"""Generate the extraction figure: chips go into a model, tokens come out, and
each extraction strategy keeps some of them.

Writes _extraction/extraction.svg, which {{< extraction >}} inlines into a
slide, and the chip images it shows to images/lc-dataset/chips/. The chips are
read from the open gelos-fm bucket (and kept in _extraction/cache/); the model,
its inputs and the strategies' slices are read from one gelos-lc config. This
script owns the geometry and the step at which each layer appears;
extraction.css owns colour and motion. Run with `pixi run extraction-figure`
and commit the output; never edit the SVG by hand.
"""

import argparse
import re
import urllib.request
from pathlib import Path

import numpy as np
import tifffile
import yaml
from PIL import Image

CONFIG = "exp010_terramind_v1_large"  # the gelos-lc config the figure is drawn from
CHIP_ID = 44914  # the chip shown as input
PATCH = {  # ViT patch size in px; the configs don't state it
    "prithvi_eo_v2_300": 16,
    "prithvi_eo_v2_300_tl_coords": 16,
    "prithvi_eo_v2_600": 14,
    "prithvi_eo_v2_600_tl_coords": 14,
    "terramind_v1_base": 16,
    "terramind_v1_large": 16,
}

BUCKET = "https://gelos-fm.s3.amazonaws.com"
# Key in a config's data.init_args.bands -> file prefix in the bucket, row label
MODALITIES = {
    "S2L2A": ("s2l2a", "S2 L2A"),
    "S1RTC": ("s1rtc", "S1 RTC"),
    "LC2L2": ("lc2l2", "Landsat"),
    "DEM": ("dem", "DEM"),
}
SEASONS = ["Jan–Mar", "Apr–Jun", "Jul–Sep", "Oct–Dec"]
CHIP_PX = 96  # a chip at 10 m, the grid the models see
CHIP_NOTE = f"chip {CHIP_ID:06} · {CHIP_PX} × {CHIP_PX} px at 10 m"
EXPORT_PX = 192  # side of the written PNGs; pixels are repeated, never smoothed

ROOT = Path(__file__).resolve().parent.parent
HERE = Path(__file__).resolve().parent
OUT = HERE / "extraction.svg"
CACHE = HERE / "cache"
CHIPS = ROOT / "images/lc-dataset/chips"

# Storyboard: the fragment index at which each layer appears (0 is the input
# chips beside the idle model). Then one step per extraction strategy.
PATCH_STEP = 1
ENCODE_STEP = 2
FIRST_STRATEGY_STEP = 3

# Geometry, in SVG user units (= px on the slide, whose text area is 1440 wide)
VIEW_W, VIEW_H = 1440, 647
CHIP, CHIP_GAP = 64, 6
CHIP_X, CHIP_Y = 90, 28
MODEL_X, MODEL_W, MODEL_TALL, MODEL_SHORT = 424, 200, 220, 130
OUT_X = 690  # where the model's output turns down towards the tokens
GRID_Y, GRID_H, GRID_GAP = 364, 259, 40
READOUT_X, READOUT_Y, ROW_H, SLICE_H = 730, 44, 84, 26
VIRIDIS = ["#440154", "#3b528b", "#21918c", "#5ec962", "#fde725"]  # the DEM chip
PLASMA = ["#0d0887", "#7e03a8", "#cc4778", "#f89540", "#f0f921"]  # the tokens


# ---- Chips: fetch from the bucket, render to PNG ---------------------------


def fetch(query, name):
    """A file from the bucket, downloaded once and then read from the cache."""
    path = CACHE / name
    if not path.exists():
        CACHE.mkdir(exist_ok=True)
        for attempt in range(3):
            try:
                with urllib.request.urlopen(f"{BUCKET}/{query}", timeout=20) as r:
                    path.write_bytes(r.read())
                break
            except OSError as e:
                if attempt == 2:
                    raise SystemExit(f"Could not fetch {BUCKET}/{query}: {e}")
    return path


def chip_files(prefix):
    """A chip's files for one modality, in date order (the bucket is listable)."""
    stem = f"data/{prefix}_{CHIP_ID:06}"
    listing = fetch(f"?list-type=2&prefix={stem}", f"{prefix}_{CHIP_ID:06}.xml")
    keys = sorted(re.findall(rf"<Key>({stem}(?:_\d+)?\.tif)</Key>", listing.read_text()))
    expected = 1 if prefix == "dem" else len(SEASONS)
    if len(keys) != expected:
        raise SystemExit(f"Expected {expected} {prefix} files for chip {CHIP_ID}, found {len(keys)}")
    return [fetch(k, Path(k).name) for k in keys]


def reflectance_rgb(a, white):
    """True colour from bands 4, 3, 2, which Sentinel-2 and Landsat both keep at 3, 2, 1."""
    return np.clip(a[..., [3, 2, 1]].astype(float) / white, 0, 1)


def s1_rgb(a):
    """False colour: VV, VH and their ratio, in dB."""
    db = 10 * np.log10(np.clip(a.astype(float), 1e-6, None))
    vv, vh = db[..., 0], db[..., 1]
    bands = [(vv + 25) / 25, (vh + 30) / 25, (vv - vh) / 15]
    return np.clip(np.dstack(bands), 0, 1)


def ramp(z, colors):
    """Values in [0, 1] through a colour map given as evenly spaced hex stops."""
    z = np.clip(np.nan_to_num(z), 0, 1) * (len(colors) - 1)
    stops = np.array([[int(c[i : i + 2], 16) for i in (1, 3, 5)] for c in colors]) / 255
    lo = np.clip(z.astype(int), 0, len(colors) - 2)
    return stops[lo] + (stops[lo + 1] - stops[lo]) * (z - lo)[..., None]


def dem_rgb(a):
    """Elevation stretched over the chip's own range."""
    a = a.astype(float)
    return ramp((a - a.min()) / max(a.max() - a.min(), 1e-6), VIRIDIS)


RENDER = {
    "s2l2a": lambda a: reflectance_rgb(a, 4000),  # digital numbers
    "lc2l2": lambda a: reflectance_rgb(a, 0.25),  # surface reflectance
    "s1rtc": s1_rgb,
    "dem": dem_rgb,
}


def render_chips():
    """Write every modality's PNGs; return {prefix: [file name]} and S2 as arrays."""
    CHIPS.mkdir(parents=True, exist_ok=True)
    names, s2 = {}, []
    for prefix, _ in MODALITIES.values():
        names[prefix] = []
        for t, path in enumerate(chip_files(prefix)):
            rgb = (RENDER[prefix](tifffile.imread(path)) * 255).round().astype(np.uint8)
            if prefix == "s2l2a":
                s2.append(rgb)
            name = "dem.png" if prefix == "dem" else f"{prefix}_{t}.png"
            Image.fromarray(rgb).resize((EXPORT_PX, EXPORT_PX), Image.NEAREST).save(CHIPS / name)
            names[prefix].append(name)
    return names, s2


# ---- Config: what goes in, what comes out, what each strategy keeps --------


class Experiment:
    def __init__(self, path):
        cfg = yaml.safe_load(path.read_text())
        data, model = cfg["data"]["init_args"], cfg["model"]
        self.name = path.stem
        self.title = model["title"]
        self.used = [MODALITIES[k][0] for k in data["bands"]]
        # Single images that are fed in again at every time step, like the DEM
        self.repeated = [MODALITIES[k][0] for k in data.get("repeat_bands") or {}]
        self.has_cls = bool(model["init_args"].get("has_cls"))
        self.strategies = cfg["embedding_extraction_strategies"]

        name = model["init_args"]["model"]
        if name not in PATCH:
            raise SystemExit(f"Add the patch size of {name} to PATCH")
        self.patch = PATCH[name]

        # The side the model sees: chips are padded or resized on the way in
        self.side, self.padded = CHIP_PX, False
        for t in data.get("transform", []):
            args = t.get("init_args", {})
            if t["class_path"].endswith(".PadIfNeeded"):
                self.side, self.padded = max(self.side, args["min_height"]), True
            elif t["class_path"].endswith(".Resize"):
                self.side, self.padded = args["height"], False
        if self.side % self.patch:
            raise SystemExit(f"{self.side} px is not a whole number of {self.patch} px patches")
        self.n = self.side // self.patch  # patches per side
        self.steps = len(SEASONS)

        # The embedding as the config's slices see it: tokens are (step, patch),
        # in one flat list or, for models that keep time apart, a list per step
        grids = [[(t, p) for p in range(self.n**2)] for t in range(self.steps)]
        self.nested = any(len(s["slice_args"]) > 1 for s in self.strategies.values())
        if self.nested:
            self.embedding = grids
        else:
            self.embedding = ["cls"] * self.has_cls + [tok for grid in grids for tok in grid]

    def select(self, strategy):
        """The tokens a strategy keeps, as gelos.extraction.select_embedding_indices
        does it: each slice is applied to every list left by the one before."""
        level = [self.embedding]
        for a in self.strategies[strategy]["slice_args"]:
            level = [x for lst in level for x in lst[slice(a["start"], a["stop"], a["step"])]]
        if not level or any(isinstance(x, list) for x in level):
            raise SystemExit(f"{strategy} does not select tokens from this embedding")
        return level

    def index(self, token):
        """A token's position in the list its last slice indexes."""
        return token[1] if self.nested else self.embedding.index(token)

    def patch_means(self, s2):
        """Mean colour of each patch of the Sentinel-2 chips, [step][row][col]."""
        out = []
        for rgb in s2:
            canvas = np.zeros((self.side, self.side, 3))
            seen = np.zeros((self.side, self.side))
            if self.padded:
                o = (self.side - CHIP_PX) // 2
                canvas[o : o + CHIP_PX, o : o + CHIP_PX] = rgb
                seen[o : o + CHIP_PX, o : o + CHIP_PX] = 1
            else:
                i = np.arange(self.side) * CHIP_PX // self.side
                canvas, seen = rgb[i][:, i].astype(float), seen + 1
            blocks = (self.n, self.patch, self.n, self.patch)
            total = canvas.reshape(*blocks, 3).sum((1, 3))
            out.append(total / seen.reshape(blocks).sum((1, 3))[..., None])
        return out

    def token_colors(self, s2):
        """A colour per token, [step][row][col]: the brightness of the patch it
        came from, stretched over each step's 2nd–98th percentile and sent
        through a colour map, so the tokens keep the chip's layout but read as
        a feature map rather than as a copy of the chip."""
        out = []
        for m in self.patch_means(s2):
            lum = m @ [0.2126, 0.7152, 0.0722]
            lo, hi = np.nanpercentile(lum, [2, 98])
            out.append(ramp((lum - lo) / max(hi - lo, 1e-6), PLASMA) * 255)
        return out


# ---- Drawing ----------------------------------------------------------------


def num(x):
    return f"{x:.2f}".rstrip("0").rstrip(".")


def frag(name, step):
    return f'class="fragment custom {name}" data-fragment-index="{step}"'


def chip_xy(row, t):
    return CHIP_X + t * (CHIP + CHIP_GAP), CHIP_Y + row * (CHIP + CHIP_GAP)


class Figure:
    def __init__(self, exp, names, s2):
        self.exp = exp
        self.names = names
        self.colors = exp.token_colors(s2)
        self.rows = [prefix for prefix, _ in MODALITIES.values()]
        self.model_y = CHIP_Y + (len(self.rows) * (CHIP + CHIP_GAP) - CHIP_GAP) / 2
        self.note_y = chip_xy(len(self.rows), 0)[1] + 16

        # The patch grid lies on the chip as the model sees it: a padded chip
        # sits inside a slightly larger frame, a resized one fills it
        self.frame = CHIP * exp.side / CHIP_PX if exp.padded else CHIP
        self.cell = GRID_H // exp.n
        grid_w = exp.n * self.cell
        cls_w = (self.cell + GRID_GAP) * exp.has_cls
        self.grid_x = (VIEW_W - cls_w - exp.steps * grid_w - (exp.steps - 1) * GRID_GAP) / 2 + cls_w
        self.cls_x = self.grid_x - cls_w

    def token_xy(self, token):
        if token == "cls":
            return self.cls_x, GRID_Y
        t, p = token
        row, col = divmod(p, self.exp.n)
        x = self.grid_x + t * (self.exp.n * self.cell + GRID_GAP) + col * self.cell
        return x, GRID_Y + row * self.cell

    def grid_path(self, x, y, attrs=""):
        o, step = (CHIP - self.frame) / 2, self.frame / self.exp.n
        ticks = [o + k * step for k in range(self.exp.n + 1)]
        d = "".join(f"M{num(x + t)} {num(y + o)}v{num(self.frame)}" for t in ticks)
        d += "".join(f"M{num(x + o)} {num(y + t)}h{num(self.frame)}" for t in ticks)
        return f'<path d="{d}" pathLength="1"{attrs}/>'

    def image(self, prefix, t, x, y):
        return (
            f'<image href="images/lc-dataset/chips/{self.names[prefix][t]}" x="{x}" y="{y}"'
            f' width="{CHIP}" height="{CHIP}"/>'
        )

    def inputs(self):
        out = ['<g id="inputs">']
        for t, season in enumerate(SEASONS):
            x, _ = chip_xy(0, t)
            out.append(
                f'  <text class="head" x="{x + CHIP / 2:g}" y="{CHIP_Y - 10}" font-size="14"'
                f' text-anchor="middle">{season}</text>'
            )
        for row, (prefix, label) in enumerate(MODALITIES.values()):
            _, y = chip_xy(row, 0)
            state = "used" if prefix in self.exp.used else "unused"
            out.append(f'  <g id="in-{prefix}" class="{state}">')
            out.append(
                f'    <text class="name" x="{CHIP_X - 12}" y="{y + CHIP / 2 + 6:g}" font-size="17"'
                f' text-anchor="end">{label}</text>'
            )
            for t in range(len(self.names[prefix])):
                out.append(f"    {self.image(prefix, t, *chip_xy(row, t))}")
            out.append("  </g>")
        out.append(
            f'  <text class="mono note" x="{CHIP_X}" y="{self.note_y}" font-size="13">{CHIP_NOTE}</text>'
        )
        out.append("</g>")
        return out

    def used_chips(self):
        for row, prefix in enumerate(self.rows):
            if prefix in self.exp.used:
                for t in range(len(self.names[prefix])):
                    yield prefix, t, *chip_xy(row, t)

    def patchify(self):
        e = self.exp
        note = f"{e.n} × {e.n} patches of {e.patch} px"
        if e.side != CHIP_PX:
            note = f"{'padded' if e.padded else 'resized'} to {e.side} px → {note}"
        out = [f'<g id="patchify" {frag("patchify", PATCH_STEP)}>']
        for i, (_, _, x, y) in enumerate(self.used_chips()):
            out.append("  " + self.grid_path(x, y, f' style="--i: {i}"'))
        # On the chip note's line, after it: mono glyphs are 0.6 em wide
        x = CHIP_X + len(CHIP_NOTE) * 13 * 0.6 + 14
        out.append(
            f'  <text class="mono" x="{num(x)}" y="{self.note_y}" font-size="13" stroke="none">{note}</text>'
        )
        out.append("</g>")
        return out

    def model(self):
        x, y = MODEL_X, self.model_y
        x2, tall, short = x + MODEL_W, MODEL_TALL / 2, MODEL_SHORT / 2
        shape = f"M{x} {num(y - tall)}L{x2} {num(y - short)}V{num(y + short)}L{x} {num(y + tall)}Z"
        in_x = CHIP_X + len(SEASONS) * (CHIP + CHIP_GAP)
        turn_y = GRID_Y - 44
        # Wrap the model's title onto lines of at most 14 characters
        lines = [""]
        for word in self.exp.title.split():
            joined = f"{lines[-1]} {word}".strip()
            if len(joined) <= 14:
                lines[-1] = joined
            else:
                lines.append(word)
        text_y = y + 14 - (len(lines) - 1) * 15
        out = [
            '<g id="model">',
            f'  <path class="wire" d="M{in_x + 4} {num(y)}H{x - 14}M{x2} {num(y)}H{OUT_X}V{turn_y - 8}"/>',
            f'  <path class="tip" d="M{x - 4} {num(y)}l-12 -7v14z"/>',
            f'  <path class="tip" d="M{OUT_X} {turn_y + 4}l-7 -12h14z"/>',
            f'  <path class="block" d="{shape}"/>',
            f'  <path {frag("glow", ENCODE_STEP)} d="{shape}"/>',
            f'  <text class="mono label" x="{x + MODEL_W / 2 - 6:g}" y="{num(text_y - 36)}"'
            ' font-size="12" text-anchor="middle">PRETRAINED ENCODER</text>',
        ]
        for i, line in enumerate(lines):
            out.append(
                f'  <text class="title" x="{x + MODEL_W / 2 - 6:g}" y="{num(text_y + i * 30)}"'
                f' font-size="25" text-anchor="middle">{line}</text>'
            )
        out.append("</g>")
        return out

    def feed(self):
        """Copies of the model's input chips, which travel into its wide end."""
        out = [f'<g id="feed" {frag("feed", ENCODE_STEP)}>']
        for prefix, t, x, y in self.used_chips():
            dx, dy = MODEL_X + 16 - (x + CHIP / 2), self.model_y - (y + CHIP / 2)
            out += [
                f'  <g class="ghost" style="--dx: {num(dx)}px; --dy: {num(dy)}px; --i: {t}">',
                f"    {self.image(prefix, t, x, y)}",
                f"    {self.grid_path(x, y)}",
                "  </g>",
            ]
        out.append("</g>")
        return out

    def token_rect(self, token, attrs=""):
        x, y = self.token_xy(token)
        side = self.cell - 2
        return f'<rect x="{num(x + 1)}" y="{y + 1}" width="{side}" height="{side}" rx="3"{attrs}/>'

    def tokens(self):
        e, c = self.exp, self.cell
        flat = e.embedding if not e.nested else [tok for grid in e.embedding for tok in grid]
        emit_x, emit_y = OUT_X, GRID_Y - 40
        label_y, range_y = GRID_Y - 12, GRID_Y + e.n * c + 20
        out = [f'<g id="tokens" {frag("tokens", ENCODE_STEP)}>']
        if e.has_cls and not e.nested:
            x = self.cls_x + c / 2
            out += [
                f'  <text class="head" x="{num(x)}" y="{label_y}" font-size="17" text-anchor="middle">CLS</text>',
                f'  <text class="mono note" x="{num(x)}" y="{range_y}" font-size="13" text-anchor="middle">0</text>',
            ]
        for t, season in enumerate(SEASONS):
            x = self.token_xy((t, 0))[0] + e.n * c / 2
            first = e.index((t, 0))
            span = f"time {t}" if e.nested else f"{first}–{first + e.n**2 - 1}"
            out += [
                f'  <text class="head" x="{num(x)}" y="{label_y}" font-size="17" text-anchor="middle">{season}</text>',
                f'  <text class="mono note" x="{num(x)}" y="{range_y}" font-size="13" text-anchor="middle">{span}</text>',
            ]
        out.append('  <g class="cells">')
        for i, token in enumerate(flat):
            x, y = self.token_xy(token)
            fill = ""
            if token != "cls":
                t, p = token
                r, g, b = self.colors[t][p // e.n][p % e.n].round().astype(int)
                fill = f' fill="#{r:02x}{g:02x}{b:02x}"'
            move = f"--dx: {num(emit_x - x - c / 2)}px; --dy: {num(emit_y - y - c / 2)}px; --i: {i}"
            name = "tok cls" if token == "cls" else "tok"
            out.append("    " + self.token_rect(token, f' class="{name}"{fill} style="{move}"'))
        out += ["  </g>", "</g>"]

        parts = ["CLS"] * (e.has_cls and not e.nested) + [f"{e.steps} time steps × {e.n**2} patches"]
        out.append(
            f'<text id="summary" {frag("summary mono", ENCODE_STEP)} x="{OUT_X + 20}" y="{GRID_Y - 50}"'
            f' font-size="15">{len(flat)} tokens = {" + ".join(parts)}</text>'
        )
        return out

    def picks(self):
        """Per strategy: the tokens it keeps, and the patches they came from."""
        e, c = self.exp, self.cell
        size = min(15, round(c * 0.38))
        out = ['<g id="picks">']
        for k, strategy in enumerate(e.strategies):
            out.append(f'  <g id="pick-{strategy}" {frag("pick", FIRST_STRATEGY_STEP + k)}>')
            sources = {}  # (chip x, chip y, patch), once each and in order
            for i, token in enumerate(e.select(strategy)):
                x, y = self.token_xy(token)
                out += [
                    f'    <g class="kept" style="--i: {i}">',
                    f"      {self.token_rect(token)}",
                    f'      <text class="mono" x="{num(x + c / 2)}" y="{num(y + c / 2 + size * 0.36)}"'
                    f' font-size="{size}" text-anchor="middle">{e.index(token)}</text>',
                    "    </g>",
                ]
                if token == "cls":
                    continue
                t, p = token
                for prefix, chip_t, cx, cy in self.used_chips():
                    if chip_t == t or prefix in e.repeated:
                        sources[cx, cy, p] = None
            o, step = (CHIP - self.frame) / 2, self.frame / e.n
            for cx, cy, p in sources:
                out.append(
                    f'    <rect class="source" x="{num(cx + o + (p % e.n) * step)}"'
                    f' y="{num(cy + o + (p // e.n) * step)}" width="{num(step)}" height="{num(step)}"/>'
                )
            out.append("  </g>")
        out.append("</g>")
        return out

    def readout(self):
        e = self.exp
        out = [
            '<g id="readout">',
            f'  <text {frag("ro-head mono", FIRST_STRATEGY_STEP)} x="{READOUT_X}" y="{READOUT_Y - 24}"'
            f' font-size="13">{e.name}.yaml · embedding_extraction_strategies</text>',
        ]
        # A nested embedding is sliced once per level, so each slice gets a line
        # that names its level
        levels = ["time", "patch"] if e.nested else [""]
        row_h = ROW_H + SLICE_H * (len(levels) - 1)
        x = READOUT_X + 22
        for k, (strategy, cfg) in enumerate(e.strategies.items()):
            y = READOUT_Y + k * row_h
            n = len(e.select(strategy))
            out += [
                f'  <g id="ro-{strategy}" {frag("strategy", FIRST_STRATEGY_STEP + k)}>',
                f'    <rect class="bar" x="{READOUT_X}" y="{y}" width="5" height="{row_h - 22}"/>',
                f'    <text x="{x}" y="{y + 25}"><tspan class="title" font-size="26">{cfg["title"]}</tspan>'
                f'<tspan class="mono key" font-size="14" dx="14">{strategy}</tspan></text>',
            ]
            for level, a in zip(levels, cfg["slice_args"]):
                y += SLICE_H
                keys = " · ".join(
                    f"{key}: {'null' if a[key] is None else a[key]}" for key in ("start", "stop", "step")
                )
                if level:
                    out.append(f'    <text class="mono key" x="{x}" y="{y + 28}" font-size="17">{level}</text>')
                out.append(
                    f'    <text class="mono slice" x="{x + 64 * bool(level)}" y="{y + 28}" font-size="17">{keys}</text>'
                )
            out += [
                f'    <text class="mono count" x="{VIEW_W}" y="{y + 28}" font-size="17" text-anchor="end">'
                f"→ {n} token{'s' * (n != 1)}</text>",
                "  </g>",
            ]
        out.append("</g>")
        return out

    def aria_label(self):
        e = self.exp
        labels = {prefix: label for prefix, label in MODALITIES.values()}
        *first, last = [labels[p] for p in e.used]
        used = " and ".join(filter(None, [", ".join(first), last]))
        kept = "; ".join(
            f"{cfg['title']} keeps {len(e.select(s))}" for s, cfg in e.strategies.items()
        )
        return (
            f"{used} chips at four seasons are cut into {e.n} by {e.n} patches and pass through "
            f"{e.title}, which returns one token per patch per season"
            f"{' plus a CLS token' if e.has_cls else ''}. Of those tokens, {kept}."
        )

    def svg(self):
        layers = self.inputs() + self.patchify() + self.model() + self.feed()
        layers += self.tokens() + self.picks() + self.readout()
        # fill/stroke here only make the file viewable on its own; the CSS sets colour
        return [
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {VIEW_W} {VIEW_H}"'
            f' role="img" aria-label="{self.aria_label()}" fill="currentColor" stroke="none">',
            *(f"  {line}" for line in layers),
            "</svg>",
        ]


def describe(exp):
    """Say in words which tokens each strategy keeps, to check against its title."""
    for strategy, cfg in exp.strategies.items():
        kept = exp.select(strategy)
        where = []
        for t, season in enumerate(SEASONS):
            cells = [divmod(tok[1], exp.n) for tok in kept if tok != "cls" and tok[0] == t]
            if cells:
                where.append(f"{season} " + " ".join(f"r{r}c{c}" for r, c in cells))
        where = ["CLS"] * ("cls" in kept) + where
        print(f"  {strategy} ({cfg['title']}): {'; '.join(where)}")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--gelos-lc", type=Path, default=ROOT.parent / "gelos-lc")
    args = ap.parse_args()
    path = args.gelos_lc / "configs" / f"{CONFIG}.yaml"
    if not path.is_file():
        raise SystemExit(f"No {path}; pass --gelos-lc")

    exp = Experiment(path)
    names, s2 = render_chips()
    OUT.write_text("\n".join(Figure(exp, names, s2).svg()) + "\n", encoding="utf-8")
    print(f"Wrote {OUT.relative_to(ROOT)} and {CHIPS.relative_to(ROOT)}/ from {CONFIG}, chip {CHIP_ID}")
    print(f"Patches are {exp.n} × {exp.n} per time step, rows and columns counted from 0:")
    describe(exp)


if __name__ == "__main__":
    main()
