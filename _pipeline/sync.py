"""Build pipeline-diagram data from the gelos-lc configs.

Writes one JSON file to _pipeline/data/ per comparison (<comparison>.json) and
per experiment and extraction strategy (<experiment>.<strategy>.json), and
copies the figures that slides reference (via {{< pipeline ... >}}) into
images/. Also writes the config excerpts listed in excerpts.yml to
_pipeline/data/excerpts/, for {{< config ... >}}, and the tool catalog from
labels.yml to _pipeline/data/tools.json, for the shortcode's `tools=` kwarg. Run with `pixi run sync`;
commit the output, since the publish workflow has no access to the other
repos.
"""

import argparse
import json
import re
import shutil
from pathlib import Path

import yaml

from excerpt import Excerpt

ROOT = Path(__file__).resolve().parent.parent
HERE = Path(__file__).resolve().parent
STAGES = ["source", "generate", "extract", "transform", "model"]
SHORTCODE = re.compile(r"\{\{<\s*pipeline\s+([^>]*?)\s*>\}\}")
# Characters of an option's config line that fit in its box (see pipeline.js)
LINE_CHARS = 26
# What an experiment runs, compared by a comparison's diff; names, extraction
# strategies and plots are left out
DIFF_KEYS = ("data", "model", "cloud_embedding")
# A diff with more rows than this is no longer a diff worth showing
DIFF_ROWS = 40


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


def config_line(key, value):
    """`key: value` as a config has it, or the value alone if that is too long
    to fit under an option's label."""
    line = f"{key}: {value}"
    return line if len(line) <= LINE_CHARS else str(value)


def changes(a, b, path=()):
    """Key paths at which config `b` differs from `a`, as (path, in a, in b),
    in b's order. Lists are compared whole, and titles not at all."""
    if isinstance(a, dict) and isinstance(b, dict):
        for k in [*b, *(k for k in a if k not in b)]:
            if k == "title":
                continue
            if k not in a or k not in b:
                yield (*path, k), k in a, k in b
            else:
                yield from changes(a[k], b[k], (*path, k))
    elif a != b:
        yield path, True, True


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

    def config_lines(self, stem, strategy, plot=None):
        """The config line that selects each stage's option for one experiment,
        by stage. Stages set by an override in labels.yml have none, since the
        config doesn't say what the option shows. `plot` is an experiment plot
        key, whose entry under the strategy gives the transform and model."""
        cfg, o = self.exps[stem], self.overrides.get(stem, {})
        lines = {}
        bands = cfg.get("data", {}).get("init_args", {}).get("bands")
        if bands and "source" not in o:
            lines["source"] = config_line("bands", ", ".join(bands))
        model = cfg.get("model") or {}
        if "generate" in o:
            pass
        elif model.get("init_args", {}).get("model"):
            lines["generate"] = config_line("model", model["init_args"]["model"])
        elif model.get("class_path"):
            lines["generate"] = model["class_path"].rsplit(".", 1)[-1]
        elif cfg.get("cloud_embedding", {}).get("backend"):
            lines["generate"] = config_line("backend", cfg["cloud_embedding"]["backend"])
        if "extract" not in o:
            lines["extract"] = strategy
        s = strategies(cfg).get(strategy, {})
        # Figures are named <transform>_<plot type> or <model type>_<plot>
        entries = [e for e in s.get("plots", []) if f"{e.get('transform')}_{e['type']}" == plot]
        entries += [e for e in s.get("models", []) if str(plot).startswith(e["type"] + "_")]
        if entries:
            lines["transform"] = config_line("transform", entries[0]["transform"])
            lines["model"] = config_line("type", entries[0]["type"])
        return lines

    def plot(self, image, src, rows, spec, sub=None, colors=None, lines=()):
        """One plot: the options it lights up per stage, and the path between
        them. `rows` are the (source, generate, extract) keys of each experiment
        behind the plot; `spec` names its transform and (optionally) model.
        `colors` are the rows' line colors in the plot, if it has any, and
        `lines` their config lines by stage (see config_lines), which go under
        the options' labels."""
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
        # Each option's config line, unless the experiments through it disagree
        found = {}
        for r, by_stage in zip(rows, lines):
            ids = dict(zip(STAGES, [f"{STAGES[i]}:{r[i]}" for i in range(3)] + [t, m]))
            for stage, line in by_stage.items():
                if ids[stage]:
                    found.setdefault(ids[stage], set()).add(line)
        under = {
            k: v.pop()
            for k, v in found.items()
            if len(v) == 1 and k not in out.get("subs", {})
        }
        if under:
            out["lines"] = under
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

    def experiment_config(self, stem, strategy, plot, chosen):
        """The lines of an experiment's config behind one of its plots, each
        tagged with the option it selects: the pipeline's config view.
        `chosen` is the plot's option ids per stage."""
        cfg, o = self.exps[stem], self.overrides.get(stem, {})
        ids = [c[:1] for c in chosen]
        ex = Excerpt(self.gelos_lc / "configs" / f"{stem}.yaml")
        ex.add(["data_version"], ids[0])
        if "source" not in o:
            ex.add(["data", "init_args", "bands"], ids[0], flow=True)
        if "generate" not in o:
            (
                ex.add(["model", "init_args", "model"], ids[1])
                or ex.add(["model", "class_path"], ids[1])
                or ex.add(["cloud_embedding", "backend"], ids[1])
            )
        at = ["embedding_extraction_strategies", strategy]
        if not ex.find(at):
            at = ["cloud_embedding", "extraction_strategies", strategy]
        ex.add([*at, "title"], ids[2])
        ex.add([*at, "slice_args"], ids[2])
        s = strategies(cfg).get(strategy, {})
        for kind in ("plots", "models"):
            for i, e in enumerate(s.get(kind, [])):
                named = f"{e.get('transform')}_{e['type']}" if kind == "plots" else e["type"] + "_"
                if plot == named or (kind == "models" and plot.startswith(named)):
                    ex.add_item([*at, kind, i], {"type": ids[4], "transform": ids[3]})
        return {"file": f"gelos-lc/configs/{stem}.yaml", "rows": ex.result()}

    def comparison_config(self, path, comp, ptype, rows, model):
        """The lines of a comparison's config behind one of its plots: each
        experiment, tagged with its Generate option, and the plot, tagged with
        the Model option."""
        ex = Excerpt(path)
        for i, r in enumerate(rows):
            fields = ("config", "strategy", "label", "color")
            ex.add_item(["experiments", i], {k: [f"generate:{r[1]}"] for k in fields})
        for i, p in enumerate(comp.get("comp_plots", [])):
            if p["type"] == ptype:
                ex.add_item(["comp_plots", i], {k: [model] if model else [] for k in ("type", "metric")})
        return {"file": f"gelos-lc/configs/comparisons/{path.name}", "rows": ex.result()}

    def diff(self, comp):
        """What sets a comparison's experiments apart: under each one's file
        name and label, the lines of its config that differ from the control's
        (the experiment labelled `control_label`, or else the first), as -/+
        rows under the keys that hold them. None if they differ by too much to
        show."""
        exps = comp["experiments"]
        labels = {
            p.get("params", {}).get("control_label")
            for p in comp.get("comp_metrics", []) + comp.get("comp_plots", [])
        }
        base = next((e for e in exps if e.get("label") in labels), exps[0])

        def head(e):
            row = {"head": f"{e['config']}.yaml", "label": e.get("label", "")}
            return {**row, "color": e["color"]} if e.get("color") else row

        def part(stem):
            return {k: v for k, v in self.exps[stem].items() if k in DIFF_KEYS}

        def excerpt(stem):
            return Excerpt(self.gelos_lc / "configs" / f"{stem}.yaml")

        rows, old = [head(base)], excerpt(base["config"])
        for e in exps:
            if e is base:
                continue
            new, above = excerpt(e["config"]), set()
            rows.append(head(e))
            for path, in_old, in_new in changes(part(base["config"]), part(e["config"])):
                for i in range(1, len(path)):
                    if path[:i] not in above:
                        above.add(path[:i])
                        rows.append((new if in_new else old).key_line(path[:i]))
                rows += old.cut(path, "-") if in_old else []
                rows += new.cut(path, "+") if in_new else []
        return {"rows": rows} if len(rows) <= DIFF_ROWS else None

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
                [self.config_lines(e["config"], e["strategy"]) for e in comp["experiments"]],
            )
            model = plots[ptype]["chosen"][4][:1]
            plots[ptype]["config"] = self.comparison_config(
                path, comp, ptype, rows, model[0] if model else None
            )
        item = self.item(name, comp.get("comparison_name", name), plots)
        diff = self.diff(comp)
        if diff:
            item["diff"] = diff
        return item

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
                f"images/experiments/{stem}/{strategy}_{key}.png",
                found[0],
                [row],
                spec,
                lines=[self.config_lines(stem, strategy, key)],
            )
            plots[key]["config"] = self.experiment_config(
                stem, strategy, key, plots[key]["chosen"]
            )
        title = cfg.get("experiment_name", stem)
        return self.item(f"{stem}.{strategy}", title, plots)

    def tools(self):
        """The tool catalog (labels.yml `tools`), by key: name, logo (None for
        a text badge) and the optional pill, caption and option fields."""
        out = {}
        for key, spec in (self.labels.get("tools") or {}).items():
            if not spec.get("name"):
                raise SystemExit(f"labels.yml: tool '{key}' has no name")
            tool = {"name": spec["name"], "logo": spec.get("logo")}
            if tool["logo"] and not (ROOT / tool["logo"]).is_file():
                raise SystemExit(f"labels.yml: tool '{key}' has no logo at {tool['logo']}")
            for field in ("pill", "caption", "option"):
                if spec.get(field):
                    tool[field] = spec[field]
            out[key] = tool
        return out

    def stages(self):
        """Full option catalog; the slide decides which options to draw. A
        stage that lists `tools` carries them, resolved from the catalog."""
        tools = self.tools()
        out = []
        for s in STAGES:
            stage = {
                "name": self.labels["stages"][s]["name"],
                "options": [{"id": f"{s}:{k}", "label": v} for k, v in self.catalog[s].items()],
            }
            keys = self.labels["stages"][s].get("tools") or []
            unknown = [k for k in keys if k not in tools]
            if unknown:
                raise SystemExit(f"labels.yml: stage '{s}' lists unknown tools {unknown}")
            if keys:
                stage["tools"] = [tools[k] for k in keys]
            out.append(stage)
        return out


def excerpts(repos):
    """The excerpts in excerpts.yml, by name: the file each is cut from and its
    rows, tagged with their region."""
    out = {}
    for name, spec in (load(HERE / "excerpts.yml") or {}).items():
        repo, _, rel = spec["file"].partition("/")
        if repo not in repos:
            raise SystemExit(f"excerpts.yml: '{name}' is from an unknown repo '{repo}'")
        path = repos[repo] / rel
        if not path.is_file():
            print(f"  warning: no {path} for excerpt '{name}'; pass --{repo}")
            continue
        ex = Excerpt(path, comments=spec.get("comments", False))
        for region, keys in spec["regions"].items():
            for key in keys:
                parts = [int(k) if k.isdigit() else k for k in key.split(".")]
                if not ex.add(parts, [region], flow=spec.get("flow", False)):
                    print(f"  warning: excerpt '{name}' has no key '{key}' in {spec['file']}")
        out[name] = {"file": spec["file"], "rows": ex.result()}
    return out


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
    ap.add_argument("--gelos-lc-datagen", type=Path, default=ROOT.parent / "gelos-lc-datagen")
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
    # The tool catalog on its own, for the shortcode's `tools=` kwarg
    (out / "tools.json").write_text(json.dumps(sync.tools(), indent=1, ensure_ascii=False) + "\n")
    cut = excerpts({"gelos-lc": args.gelos_lc, "gelos-lc-datagen": args.gelos_lc_datagen})
    (out / "excerpts").mkdir()
    for name, item in cut.items():
        (out / "excerpts" / f"{name}.json").write_text(
            json.dumps(item, indent=1, ensure_ascii=False) + "\n"
        )
    print(
        f"Wrote {n_comp} comparisons, {len(items) - n_comp} experiment strategies "
        f"and {len(cut)} excerpts to {out.relative_to(ROOT)}/"
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
