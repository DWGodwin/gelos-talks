# GELOS talks

Slides about [GELOS](https://github.com/ClarkCGA/gelos), built with [Quarto RevealJS](https://quarto.org/docs/presentations/revealjs/).

## Layout

```
full.qmd             master deck: every slide file
cng-lightning.qmd    CNG lightning talk (5 min, auto-advancing)
index.qmd            landing page linking all decks
slides/              slide files; decks include these, they never render alone
images/              figures used by slides
  comparisons/, experiments/   figures copied from gelos-lc by `pixi run sync`
videos/              screen recordings used by slides (videos/raw/ holds the originals, uncommitted)
_pipeline/           animated pipeline diagram and clip shortcodes (labels, sync script, generated data)
_extensions/
  dwgodwin/slides/   house style (format: slides-revealjs)
  dwgodwin/cng/      CNG lightning-talk style, layered on the house style (format: cng-revealjs)
```

Each deck is front matter plus a list of includes:

```markdown
{{< include slides/motivation.qmd >}}
```

## Making a new talk

1. Copy `full.qmd` to e.g. `agu-2026.qmd`.
2. Delete the includes you don't need and set the front matter (title, format, auto-slide...).
3. Add a row to the table in `index.qmd`.

## Editing slides

- Fix a slide in `slides/` and every deck that includes it picks up the change.
- Keep each file to one section of the story, written as `##` slides with an `{#id}`.
- When a talk needs a shorter or longer version of a section, add a variant file (e.g. `results.qmd` plus a full-deck-only `results-detail.qmd`) rather than editing the shared one.
- Reference images as `images/...`. Includes are pasted into the deck, so paths are relative to the deck at the repo root, not to `slides/`.
- Use the house-style helper classes (`.center-v`, `.statement`, `.hl`, `.muted`, `.two-col`, `.formula`, `.a-fade`/`.a-rise`, ...). The CNG theme is layered on the house style, so they work in either format.

## Pipeline slides

A slide can show [gelos-lc](https://github.com/ClarkCGA/gelos-lc) plots as an animated pipeline: the stages appear one by one, the path behind the plot is drawn through its options, then those options stack on the left beside the plot.

```markdown
## Prithvi 300M vs 600M {#pipeline-prithvi-scale}

{{< pipeline 01a_prithvi_family:knn_purity_plot >}}

## Inside one experiment {#pipeline-prithvi-300}

{{< pipeline
  exp001_prithvi300.all_steps_of_middle_patch:raw_temporal_cosine_similarity
  exp001_prithvi300.cls_token:random_forest_confusion_matrix
  exp001_prithvi300.cls_token:tsne_scatter_2d
>}}
```

Each argument is one view, written `<name>:<plot>`, and views are shown in the order given.

- **Comparison plots:** `<comparison>:<plot>`, where the comparison is a file name from `gelos-lc/configs/comparisons/` and the plot one of its `comp_plots` types.
- **Single-experiment plots:** `<experiment>.<strategy>:<plot>`, where the experiment is a config name, the strategy one of its extraction strategies, and the plot a key under `experiment_plots` in `_pipeline/labels.yml`.
- **Several views on one slide:** the pipeline is drawn for the first view, and each view after it adds a click. The plot swaps and only the stacked options that differ change (the model, the extraction strategy, the transform), the new one slotting in from the right as the old one slots out to the left. Every view names its own experiment, strategy and plot, so one model can use a different strategy per plot, and a model can be left out of a plot it doesn't have.
- **Skipping the build:** `start=stacked` opens the slide on the stacked options and the plot, with no clicks for the stages or the path. Use it once the audience has seen the pipeline drawn, e.g. to show the same plot for another experiment.

After adding a slide, or when configs or figures change in gelos-lc, run:

```bash
pixi run sync    # expects gelos-lc next to this repo; otherwise add --gelos-lc <path>
```

This rewrites `_pipeline/data/` from the configs and copies the figures that slides use into `images/`. Commit both: the publish workflow has no access to gelos-lc.

The slide title shows while the stages and path are drawn, then fades once the options stack, so the plot can use the full height of the slide.

Display names, the order of options, and how many are drawn before "+ N more" are set in `_pipeline/labels.yml`.

Each plot type can also have a `caption` there: one line explaining the metric, shown under the plot once the options stack (and dropped when `image=` replaces the plot). The first slide of each plot type is preceded by a question slide, an eyebrow naming the metric over the question it helps answer (see `#q-knn-purity` in `slides/pipeline_knn.qmd`).

## Screen recordings

A feature slide pairs a short description with a looping screen recording (see `slides/app.qmd`):

```markdown
## {#app-linked-views}

::: {.feature}
::: {.feature-text}
[gelos-app]{.eyebrow}

[Feature name]{.feature-title}

One or two sentences on what this feature shows.
:::

{{< clip videos/app-linked-views.mp4 >}}
:::
```

Until the file exists the slide shows a placeholder naming the path. To add a clip:

1. Record with <kbd>Cmd</kbd>+<kbd>Shift</kbd>+<kbd>5</kbd> → *Record Selected Portion*, over a 16:9 browser window.
2. Save it as `videos/raw/<name>.mov` (not committed).
3. Run `pixi run clips`, which writes `videos/<name>.mp4` (H.264, at most 1920 px wide, no audio, sped up). Commit that file.

Clips are muted, loop, and restart whenever their slide is shown. `pixi run clips` speeds them up by the factor in `_pipeline/clips.yml` (default 2×, with per-clip overrides); editing that file re-encodes every clip.

## Preview and publish

```bash
quarto preview full.qmd
```

For auto-advancing decks, add `?autoSlide=0` before the `#` in the preview URL to stop auto-advance while editing.

Pushing to `main` renders every deck and publishes `_site/` to the `gh-pages` branch. Enable Pages once under **Settings → Pages → Deploy from branch → gh-pages**. Decks are then at `https://dwgodwin.github.io/gelos-talks/<deck>.html`.

Both themes come from [quarto-slides-template](https://github.com/DWGodwin/quarto-slides-template); don't edit `_extensions/` here. To update them: `quarto add DWGodwin/quarto-slides-template`.
