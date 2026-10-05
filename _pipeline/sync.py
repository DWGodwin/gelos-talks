"""Build pipeline-diagram data from the gelos-lc configs.

Writes one JSON file to _pipeline/data/ per comparison (<comparison>.json) and
per experiment and extraction strategy (<experiment>.<strategy>.json), and
copies the figures that slides reference (via {{< pipeline ... >}}) into
images/. Run with `pixi run sync`; commit the output, since the publish
workflow has no access to gelos-lc.
"""

import argparse
import json
import re
import shutil
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
HERE = Path(__file__).resolve().parent
STAGES = ["source", "generate", "extract", "transform", "model"]
SHORTCODE = re.compile(r"\{\{<\s*pipeline\s+([^>]*?)\s*>\}\}")


def load(path):
    with open(path) as f:
        return yaml.safe_load(f)


def source_key(cfg):
    bands = cfg.get("data", {}).get("init_args", {}).get("bands") or {}
    key = f"s2_{len(bands.get('S2L2A', []))}"
    if "S1RTC" in bands:
        key += "+s1"
    if "DEM" in bands:
        key += "+dem"
    return key


def source_label(key):
    s2, *rest = key.split("+")
    if rest:
        return "+".join(["S2"] + [r.upper() for r in rest])
    return f"S2 ({s2.split('_')[1]}-band)"


def generate_key(cfg):
    model = cfg.get("model") or {}
    if "SpectralBands" in model.get("class_path", ""):
        return "spectral_bands"
    name = model.get("init_args", {}).get("model")
    if name:
        return re.sub(r"_s1s2$", "", name)
    return cfg.get("cloud_embedding", {}).get("backend", "unknown")


def strategies(cfg):
    return (
        cfg.get("embedding_extraction_strategies")
        or cfg.get("cloud_embedding", {}).get("extraction_strategies")
        or {}
    )


def k_values(cfg, strategy, metric):
    for m in strategies(cfg).get(strategy, {}).get("metrics", []):
        if m.get("type") == metric:
            return m.get("params", {}).get("k_values")
    return None


class Sync:
    def __init__(self, gelos_lc, labels):
        self.gelos_lc = gelos_lc
        self.labels = labels
        self.overrides = labels.get("experiments") or {}
        # Every option per stage: labels.yml order first, then discovered ones
        self.catalog = {s: dict(labels["stages"][s]["options"]) for s in STAGES}
        self.exps = {
            p.stem: load(p) for p in sorted((gelos_lc / "configs").glob("exp*.yaml"))
        }
        # Register every option gelos-lc knows about, so "+ N more" is accurate
        for stem, cfg in self.exps.items():
            src, gen = self.keys(stem)
            self.catalog["source"].setdefault(
                src, source_label(src) if src.startswith("s2_") else src
            )
            title = (cfg.get("model") or {}).get("title") or cfg.get("experiment_name")
            self.catalog["generate"].setdefault(gen, title)
            for skey, s in strategies(cfg).items():
                self.catalog["extract"].setdefault(skey, s.get("title", skey))
        self.sources = {}  # image path in this repo -> figure in gelos-lc

    def keys(self, stem):
        """(source, generate) option keys for an experiment config."""
        o = self.overrides.get(stem, {})
        cfg = self.exps[stem]
        return o.get("source", source_key(cfg)), o.get("generate", generate_key(cfg))

    def plot(self, image, src, rows, spec, sub=None, colors=None):
        """One plot: the options it lights up per stage, and the path between
        them. `rows` are the (source, generate, extract) keys of each experiment
        behind the plot; `spec` names its transform and (optionally) model.
        `colors` are the rows' line colors in the plot, if it has any."""
        self.sources[image] = src
        t = f"transform:{spec['transform']}"
        m = f"model:{spec['model']}" if spec.get("model") else None
        chosen = [
            list(dict.fromkeys(f"{STAGES[i]}:{r[i]}" for r in rows)) for i in range(3)
        ]

        def pairs(i):
            return sorted({(f"{STAGES[i]}:{r[i]}", f"{STAGES[i + 1]}:{r[i + 1]}") for r in rows})

        out = {
            "image": image,
            "chosen": chosen + [[t], [m] if m else []],
            # One list of [from, to] option ids per gap between stages
            "links": [pairs(0), pairs(1), [(x, t) for x in chosen[2]], [(t, m)] if m else []],
        }
        if sub and m:
            out["subs"] = {m: sub}
        if colors:
            # Each Generate option's colors in the plot, one per experiment
            # through it (a model can appear under several inputs)
            keys = {}
            for r, c in zip(rows, colors):
                ids = keys.setdefault(f"generate:{r[1]}", [])
                if c and c not in ids:
                    ids.append(c)
            out["colors"] = {k: v for k, v in keys.items() if v}
        if spec.get("caption"):
            out["caption"] = spec["caption"]
        return out

    def item(self, name, title, plots):
        return {
            "name": name,
            "title": title,
            "max_options": self.labels.get("max_options", 5),
            "plots": plots,
        }

    def comparison(self, path):
        comp = load(path)
        name = path.stem
        rows = [
            (*self.keys(e["config"]), self.overrides.get(e["config"], {}).get("extract", e["strategy"]))
            for e in comp["experiments"]
        ]
        colors = [e.get("color") for e in comp["experiments"]]
        plots = {}
        for p in comp.get("comp_plots", []):
            ptype = p["type"]
            spec = (self.labels.get("plots") or {}).get(ptype)
            if spec is None:
                # Unmapped plot type: show it as its own Model option
                spec = {"transform": "none", "model": ptype}
                self.catalog["model"].setdefault(ptype, ptype.replace("_", " ").capitalize())
                print(f"  note: plot type '{ptype}' is not in labels.yml (used by {name})")
            sub = None
            if spec.get("k"):
                first = comp["experiments"][0]
                ks = k_values(self.exps[first["config"]], first["strategy"], spec["k"])
                sub = ks and "k = " + ", ".join(map(str, ks))
            plots[ptype] = self.plot(
                f"images/comparisons/{name}/{ptype}.png",
                self.gelos_lc / "reports/figures/comparisons" / name / f"{ptype}.png",
                rows,
                spec,
                sub,
                colors,
            )
        return self.item(name, comp.get("comparison_name", name), plots)

    def experiment(self, stem, strategy):
        """Plots of one experiment and strategy, found by their figure files."""
        cfg = self.exps[stem]
        figures = self.gelos_lc / "reports/figures" / str(cfg.get("data_version")) / stem
        row = (*self.keys(stem), strategy)
        plots = {}
        for key, spec in (self.labels.get("experiment_plots") or {}).items():
            found = sorted(figures.glob(f"{strategy}_*_{key}.png"))
            if not found:
                continue
            if len(found) > 1:
                print(f"  note: {stem}.{strategy} has {len(found)} '{key}' figures; using {found[0].name}")
            plots[key] = self.plot(
                f"images/experiments/{stem}/{strategy}_{key}.png", found[0], [row], spec
            )
        title = cfg.get("experiment_name", stem)
        return self.item(f"{stem}.{strategy}", title, plots)

    def stages(self):
        """Full option catalog; the slide decides which options to draw."""
        return [
            {
                "name": self.labels["stages"][s]["name"],
                "options": [{"id": f"{s}:{k}", "label": v} for k, v in self.catalog[s].items()],
            }
            for s in STAGES
        ]


def slide_uses():
    """(data file name, plot) for every view in the slides' shortcodes."""
    uses = set()
    for qmd in ROOT.rglob("*.qmd"):
        if any(part.startswith((".", "_")) for part in qmd.relative_to(ROOT).parts):
            continue
        for body in SHORTCODE.findall(qmd.read_text()):
            args = body.split()
            if any(a.startswith("image=") for a in args):
                continue  # the slide brings its own image
            for view in args:
                if "=" not in view:
                    name, _, plot = view.partition(":")
                    uses.add((name, plot))
    return uses


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--gelos-lc", type=Path, default=ROOT.parent / "gelos-lc")
    args = ap.parse_args()
    if not (args.gelos_lc / "configs").is_dir():
        raise SystemExit(f"No configs directory in {args.gelos_lc}; pass --gelos-lc")

    sync = Sync(args.gelos_lc, load(HERE / "labels.yml"))
    items = {}
    for path in sorted((args.gelos_lc / "configs/comparisons").glob("*.yaml")):
        items[path.stem] = sync.comparison(path)
    n_comp = len(items)
    for stem, cfg in sync.exps.items():
        for strategy in strategies(cfg):
            item = sync.experiment(stem, strategy)
            if item["plots"]:
                items[item["name"]] = item

    # Comparisons can add catalog options, so attach stages once all are built
    stages = sync.stages()
    out = HERE / "data"
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir()
    for name, item in items.items():
        item["stages"] = stages
        (out / f"{name}.json").write_text(json.dumps(item, indent=1, ensure_ascii=False) + "\n")
    print(
        f"Wrote {n_comp} comparisons and {len(items) - n_comp} experiment strategies "
        f"to {out.relative_to(ROOT)}/"
    )

    # Copy only the figures that slides use
    for name, plot in sorted(slide_uses()):
        if name not in items:
            print(f"  warning: slide uses unknown pipeline '{name}'")
            continue
        if plot not in items[name]["plots"]:
            print(f"  warning: '{name}' has no plot '{plot}'")
            continue
        image = items[name]["plots"][plot]["image"]
        src = sync.sources[image]
        if not src.exists():
            print(f"  warning: missing figure {src}")
            continue
        (ROOT / image).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, ROOT / image)
        print(f"  copied {image}")


if __name__ == "__main__":
    main()
