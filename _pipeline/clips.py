"""Convert screen recordings to small, web-ready MP4s.

Reads every recording in videos/raw/ (the .mov files macOS produces, or any
other video) and writes videos/<name>.mp4: H.264, at most 1920 px wide, 30 fps,
no audio, sped up by the factor set in _pipeline/clips.yml. A recording listed
under `parts` there is also cut into several clips, each from a span of the
recording. Recordings that are already converted and unchanged (and whose
settings are unchanged) are skipped. Run with `pixi run clips`.
"""

import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "videos" / "raw"
CONFIG = Path(__file__).resolve().parent / "clips.yml"


def convert(src, dst, speed, start=None, end=None):
    """Write src to dst, sped up, cut to [start, end] seconds of src if given."""
    span = []
    if start is not None:
        span += ["-ss", str(start)]
    if end is not None:
        # -t, not -to: with -ss before -i, timestamps restart at the cut
        span += ["-t", str(end - (start or 0))]
    subprocess.run(
        [
            "ffmpeg", "-y", "-loglevel", "error", *span, "-i", str(src),
            # even dimensions are required by H.264
            "-vf", f"setpts=PTS/{speed},scale='min(1920,iw)':-2,fps=30",
            "-c:v", "libx264", "-crf", "24", "-preset", "slow",
            "-pix_fmt", "yuv420p", "-an", "-movflags", "+faststart",
            str(dst),
        ],
        check=True,
    )
    mb = dst.stat().st_size / 1e6
    cut = ""
    if start is not None or end is not None:
        cut = f", from {start or 0:g} s to {'the end' if end is None else f'{end:g} s'}"
    print(f"  wrote {dst.relative_to(ROOT)} ({speed:g}x{cut}, {mb:.1f} MB)")


def main():
    with open(CONFIG) as f:
        config = yaml.safe_load(f) or {}
    default = float(config.get("default", 1))
    speeds = config.get("speeds") or {}
    parts = config.get("parts") or {}
    RAW.mkdir(parents=True, exist_ok=True)
    sources = sorted(p for p in RAW.iterdir() if p.is_file() and not p.name.startswith("."))
    if not sources:
        print(f"No recordings in {RAW.relative_to(ROOT)}/")
    for src in sources:
        speed = float(speeds.get(src.stem, default))
        newest = max(src.stat().st_mtime, CONFIG.stat().st_mtime)
        outputs = [(src.stem, None, None)]
        for part in parts.get(src.stem) or []:
            if "name" not in part or not ({"start", "end"} & part.keys()):
                raise SystemExit(f"clips.yml: a part of {src.stem} needs a name and a start or end")
            outputs.append((part["name"], part.get("start"), part.get("end")))
        for name, start, end in outputs:
            dst = ROOT / "videos" / (name.replace(" ", "-") + ".mp4")
            if dst.exists() and dst.stat().st_mtime >= newest:
                print(f"  up to date: {dst.relative_to(ROOT)}")
                continue
            convert(src, dst, speed, start, end)


if __name__ == "__main__":
    main()
