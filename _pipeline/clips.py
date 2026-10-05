"""Convert screen recordings to small, web-ready MP4s.

Reads every recording in videos/raw/ (the .mov files macOS produces, or any
other video) and writes videos/<name>.mp4: H.264, at most 1920 px wide, 30 fps,
no audio, sped up by the factor set in _pipeline/clips.yml. Recordings that are
already converted and unchanged (and whose speed is unchanged) are skipped.
Run with `pixi run clips`.
"""

import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "videos" / "raw"
CONFIG = Path(__file__).resolve().parent / "clips.yml"


def main():
    with open(CONFIG) as f:
        config = yaml.safe_load(f) or {}
    default = float(config.get("default", 1))
    speeds = config.get("speeds") or {}
    RAW.mkdir(parents=True, exist_ok=True)
    sources = sorted(p for p in RAW.iterdir() if p.is_file() and not p.name.startswith("."))
    if not sources:
        print(f"No recordings in {RAW.relative_to(ROOT)}/")
    for src in sources:
        dst = ROOT / "videos" / (src.stem.replace(" ", "-") + ".mp4")
        newest = max(src.stat().st_mtime, CONFIG.stat().st_mtime)
        if dst.exists() and dst.stat().st_mtime >= newest:
            print(f"  up to date: {dst.relative_to(ROOT)}")
            continue
        speed = float(speeds.get(src.stem, default))
        subprocess.run(
            [
                "ffmpeg", "-y", "-loglevel", "error", "-i", str(src),
                # even dimensions are required by H.264
                "-vf", f"setpts=PTS/{speed},scale='min(1920,iw)':-2,fps=30",
                "-c:v", "libx264", "-crf", "24", "-preset", "slow",
                "-pix_fmt", "yuv420p", "-an", "-movflags", "+faststart",
                str(dst),
            ],
            check=True,
        )
        mb = dst.stat().st_size / 1e6
        print(f"  wrote {dst.relative_to(ROOT)} ({speed:g}x, {mb:.1f} MB)")


if __name__ == "__main__":
    main()
