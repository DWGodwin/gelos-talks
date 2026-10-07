"""Generate the grid-alignment figure: why GELOS chips are 960 m on a side.

Writes _grid/grid-alignment.svg, which {{< grid-alignment >}} inlines into a
slide. This script owns the geometry (1 SVG user unit = 1 m, origin at the
top-left corner of the grids) and the step at which each layer appears;
grid-alignment.css owns colour and motion. Run with `pixi run grid-figure` and
commit the output; never edit the SVG by hand.
"""

from fractions import Fraction
from math import lcm
from pathlib import Path

CHIP_CANDIDATES = [160, 320, 640, 960]  # chip sides in m, in the order they are tried
PATCH = 16  # ViT patch size in px
BANDS = {10: "s2", 30: "ls"}  # pixel size in m -> sensor

SENSORS = {"s2": "Sentinel-2", "ls": "Landsat"}
OUT = Path(__file__).resolve().parent / "grid-alignment.svg"

SIZES = sorted(BANDS)
LCM = lcm(*(PATCH * b for b in SIZES))  # smallest side every band tiles
ANSWER = CHIP_CANDIDATES[-1]  # the side settled on: a multiple of LCM, for more context per chip
EXTENT = ANSWER  # the grids are drawn one chip wide, so the answer fills them
MARGIN = 20
VIEW_H = EXTENT + 2 * MARGIN
VIEW_W = VIEW_H * 3 // 2

# Storyboard: the fragment index at which each layer appears (0 is the blank
# canvas). Pixel grids: one per step, finest first. Patch grids: finest, then
# the rest together. Then one step per candidate, then the caption.
GRID_STEP = {b: i + 1 for i, b in enumerate(SIZES)}
FIRST_PATCH_STEP = len(SIZES) + 1
PATCH_STEP = {b: FIRST_PATCH_STEP + min(i, 1) for i, b in enumerate(SIZES)}
FIRST_CHIP_STEP = FIRST_PATCH_STEP + 2
CHIP_STEP = {c: FIRST_CHIP_STEP + i for i, c in enumerate(CHIP_CANDIDATES)}
CAPTION_STEP = FIRST_CHIP_STEP + len(CHIP_CANDIDATES)

# Readout panel, to the right of the grids: a legend row per band from the top,
# the candidate block and the caption at the bottom
PANEL_X = EXTENT + 60
ROW_H = 190
TEXT_X = PANEL_X + 33
CAND_Y = 740  # baseline of the CANDIDATE CHIP label; the size sits 110 below it
VERDICT_X, VERDICT_Y, VERDICT_SIZE = PANEL_X + 350, CAND_Y + 30, 85
CAPTION_Y = 950
TAG_W, TAG_H = 125, 45


def pixel_stroke(band):
    return round(0.64 + band * 0.036, 1)


def patch_stroke(band):
    return round(0.5 + band * 0.16, 1)


def fits(chip, band):
    return chip % (PATCH * band) == 0


def num(x):
    return f"{float(x):.2f}".rstrip("0").rstrip(".")


def readout(chip, band):
    px = Fraction(chip, band)
    patches = px / PATCH
    return f"{num(px)} px → {num(patches)} {'patch' if patches == 1 else 'patches'}"


def verdict(chip):
    return "ok" if all(fits(chip, b) for b in SIZES) else "bad"


def frag(name, step):
    return f'class="fragment custom {name}" data-fragment-index="{step}"'


def pixel_grid(band):
    ticks = range(0, EXTENT + 1, band)
    d = "".join(f"M{x} 0v{EXTENT}" for x in ticks) + "".join(f"M0 {y}h{EXTENT}" for y in ticks)
    return [
        f'<g id="grid-{band}" {frag(f"pixels {BANDS[band]}", GRID_STEP[band])}'
        f' stroke-width="{pixel_stroke(band)}">',
        f'  <path d="{d}"/>',
        "</g>",
    ]


def patch_grid(band):
    # --i counts lines out from the top-left corner, so the draw-on can sweep
    out = [
        f'<g id="patch-{band}" {frag(f"patches patch {BANDS[band]}", PATCH_STEP[band])}'
        f' stroke-width="{patch_stroke(band)}">'
    ]
    for k, t in enumerate(range(0, EXTENT + 1, PATCH * band)):
        out.append(f'  <line x1="{t}" y1="0" x2="{t}" y2="{EXTENT}" pathLength="1" style="--i: {k}"/>')
        out.append(f'  <line x1="0" y1="{t}" x2="{EXTENT}" y2="{t}" pathLength="1" style="--i: {k}"/>')
    out.append("</g>")
    return out


def chip_outline(i, side):
    # --from is the previous candidate's side, so the outline can resize from it
    start = CHIP_CANDIDATES[i - 1] if i else side
    name = f"chip {'resize' if i else 'draw'} {verdict(side)}"
    return [
        f'<g id="chip-{side}" {frag(name, CHIP_STEP[side])}'
        f' style="--from: {start}px; --to: {side}px" stroke-width="4">',
        f'  <rect class="outline" width="{side}" height="{side}" pathLength="1"/>',
        '  <g class="tag">',
        f'    <rect x="{side - TAG_W}" y="{side - TAG_H}" width="{TAG_W}" height="{TAG_H}"/>',
        f'    <text x="{side - TAG_W / 2:g}" y="{side - 12}" font-size="32" text-anchor="middle"'
        f' fill="currentColor" stroke="none">{side} m</text>',
        "  </g>",
        "</g>",
    ]


def readout_panel():
    out = ['<g id="readout" fill="currentColor" stroke="none">']
    for row, band in enumerate(SIZES):
        y = row * ROW_H
        sensor = BANDS[band]
        out += [
            f'  <g id="ro-band-{band}" {frag("ro-band", GRID_STEP[band])}>',
            f'    <rect class="swatch {sensor}" x="{PANEL_X}" y="{y + 7}" width="21" height="21"/>',
            f'    <text class="name" x="{TEXT_X}" y="{y + 29}" font-size="32">'
            f"{SENSORS[sensor]} {band} m</text>",
            "  </g>",
            f'  <g id="ro-patch-{band}" {frag("ro-patch", PATCH_STEP[band])}>',
            f'    <line class="patch {sensor}" x1="{PANEL_X}" y1="{y + 57.5}" x2="{PANEL_X + 21}"'
            f' y2="{y + 57.5}" stroke="currentColor" stroke-width="{patch_stroke(band)}"/>',
            f'    <text class="mono" x="{TEXT_X}" y="{y + 65}" font-size="23">'
            f"{PATCH} px patch = {PATCH * band} m</text>",
            "  </g>",
        ]
    for chip in CHIP_CANDIDATES:
        out.append(f'  <g id="ro-{chip}" {frag("ro-cand", CHIP_STEP[chip])}>')
        for row, band in enumerate(SIZES):
            state = "ok" if fits(chip, band) else "bad"
            out.append(
                f'    <text id="ro-{band}-{chip}" class="row mono {state}" x="{TEXT_X}"'
                f' y="{row * ROW_H + 106}" font-size="28" style="--i: {row}">{readout(chip, band)}</text>'
            )
        out += [
            f'    <text class="label mono" x="{PANEL_X}" y="{CAND_Y}" font-size="20">CANDIDATE CHIP</text>',
            f'    <text class="size" x="{PANEL_X}" y="{CAND_Y + 110}" font-size="100">{chip} m</text>',
            "  </g>",
        ]
    out.append("</g>")
    return out


def verdict_mark(chip):
    x, y, s = VERDICT_X, VERDICT_Y, VERDICT_SIZE
    state = verdict(chip)
    out = [
        f'<g id="verdict-{chip}" {frag(f"verdict {state}", CHIP_STEP[chip])}'
        ' stroke-width="14" stroke-linecap="round" stroke-linejoin="round">'
    ]
    if state == "ok":
        out.append(
            f'  <path d="M{x} {y + s * 0.55:g}L{x + s * 0.36:g} {y + s * 0.9:g}L{x + s} {y + s * 0.1:g}"'
            ' pathLength="1"/>'
        )
    else:
        out.append(f'  <line x1="{x}" y1="{y}" x2="{x + s}" y2="{y + s}" pathLength="1" style="--i: 0"/>')
        out.append(f'  <line x1="{x + s}" y1="{y}" x2="{x}" y2="{y + s}" pathLength="1" style="--i: 1"/>')
    out.append("</g>")
    return out


def caption():
    sides = ", ".join(str(PATCH * b) for b in SIZES)
    factor = ANSWER // LCM
    times = f"{factor} × " if factor > 1 else ""
    return [
        f'<g id="caption" {frag("caption", CAPTION_STEP)} fill="currentColor" stroke="none">',
        f'  <text class="mono" x="{PANEL_X}" y="{CAPTION_Y}" font-size="23">'
        f'<tspan class="hl">{ANSWER} m</tspan> = {times}lcm({sides})</text>',
        "</g>",
    ]


def aria_label():
    def listed(sensor):
        sizes = [str(b) for b in SIZES if BANDS[b] == sensor]
        return f"{SENSORS[sensor]} {' and '.join(filter(None, [', '.join(sizes[:-1]), sizes[-1]]))} m"

    bands = " and ".join(listed(s) for s in SENSORS if s in BANDS.values())
    tiles = (
        f"{bands} bands all cut into whole {PATCH} by {PATCH} pixel patches, "
        "with patch borders that coincide across sensors"
    )
    if ANSWER == LCM:
        return f"A {ANSWER} m chip is the smallest square that {tiles}."
    *failing, last = CHIP_CANDIDATES[:-1]
    tried = f"{', '.join(f'{c} m' for c in failing)} and {last} m" if failing else f"{last} m"
    return (
        f"Chips of {tried} leave some bands with part-patches. A {ANSWER} m chip, "
        f"{ANSWER // LCM} times the {LCM} m least common multiple, is the first square past "
        f"{last} m that {tiles}."
    )


def main():
    # The figure ends on the last candidate as the answer; refuse to draw a false claim
    *failing, answer = CHIP_CANDIDATES
    if verdict(answer) != "ok" or answer % LCM or any(verdict(c) == "ok" for c in failing):
        raise SystemExit(
            f"CHIP_CANDIDATES must end on a multiple of lcm = {LCM} m, after candidates that fail "
            f"to tile every band, got {CHIP_CANDIDATES}"
        )

    layers = []
    for band in SIZES:
        layers += pixel_grid(band)
    for band in SIZES:
        layers += patch_grid(band)
    for i, side in enumerate(CHIP_CANDIDATES):
        layers += chip_outline(i, side)
    layers += readout_panel()
    for side in CHIP_CANDIDATES:
        layers += verdict_mark(side)
    layers += caption()

    # fill/stroke here only make the file viewable on its own; the CSS sets colour
    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{-MARGIN} {-MARGIN} {VIEW_W} {VIEW_H}"'
        f' role="img" aria-label="{aria_label()}" fill="none" stroke="currentColor">',
        *(f"  {line}" for line in layers),
        "</svg>",
    ]
    OUT.write_text("\n".join(svg) + "\n", encoding="utf-8")
    print(f"Wrote {OUT.relative_to(OUT.parent.parent)}")


if __name__ == "__main__":
    main()
