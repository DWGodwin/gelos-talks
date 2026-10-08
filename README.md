# GELOS talks

Slides about [GELOS](https://github.com/ClarkCGA/gelos), built with [Quarto RevealJS](https://quarto.org/docs/presentations/revealjs/).

## Layout

```
full.qmd             master deck: every slide file
cng-lightning.qmd    CNG lightning talk (20 slides × 15 s, auto-advancing): GELOS Land Cover and the app
index.qmd            landing page linking all decks
slides/              slide files; decks include these, they never render alone
images/              figures used by slides
  comparisons/, experiments/   figures copied from gelos-lc by `pixi run sync`
videos/              screen recordings used by slides (videos/raw/ holds the originals, uncommitted)
_pipeline/           animated pipeline diagram, config panel and clip shortcodes (labels, excerpt list, sync script, generated data)
_grid/               animated grid-alignment figure (generator, generated SVG, CSS, shortcode)
_extraction/         animated extraction figure (generator, generated SVG, CSS, shortcode)
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
2. Delete the includes you don't need and set the front matter (pagetitle, format, auto-slide...). Use `pagetitle`, not `title`: `title` makes Quarto add its own title slide in front of `slides/title.qmd`.
3. Add a row to the table in `index.qmd`.

## Editing slides

- Fix a slide in `slides/` and every deck that includes it picks up the change.
- Keep each file to one section of the story, written as `##` slides with an `{#id}`.
- `slides/title.qmd` opens every deck and `slides/thanks.qmd` closes it; include both in any new deck.
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
- **Config lines:** when the path is drawn, each option it passes through shows the line of the experiment's config that selects it (`model: prithvi_eo_v2_600`, `transform: tsne`) under its label. The lines stay on the stacked options unless the stack would have to shrink to fit them. Nothing to set: they are read from the configs, and an option whose experiments disagree shows none.
- **Showing the config:** `config=yaml` adds a click between the options stacking and the first plot. The plot's place is taken by the lines of the config behind it, cut from the real file, with each stacked option linked to the lines that select it. For a comparison, these are its experiments (their legend colors beside them) and the plot.
- **Showing what differs:** `config=diff`, for a comparison, shows in the same place what sets its experiments apart: under each one's file name and label, the lines of its config that differ from the control's (the experiment named by `control_label`, or else the first). Only the `data` and `model` sections are compared. A comparison whose experiments differ by more than about 40 lines has no diff, and the shortcode says so.
- **Timing, in auto-advancing decks:** `hold=<ms>` is how long each click from the path on (the path, the stacked options or the config, then each plot) stays on screen; the slide's `data-autoslide` then only times the clicks that draw the stages. See "Timed decks" below.

```markdown
{{< pipeline 02_across_families:knn_purity_plot config=yaml >}}

{{< pipeline 06a_prithvi300_band_ablation_middle_patch:per_class_ecdf_plot start=stacked config=diff >}}
```

After adding a slide, or when configs or figures change in gelos-lc, run:

```bash
pixi run sync    # expects gelos-lc and gelos-lc-datagen next to this repo; otherwise add --gelos-lc <path> --gelos-lc-datagen <path>
```

This rewrites `_pipeline/data/` from the configs and copies the figures that slides use into `images/`. Commit both: the publish workflow has no access to the other repos.

The slide title shows while the stages and path are drawn, then fades once the options stack, so the plot can use the full height of the slide.

Display names, the order of options, and how many are drawn before "+ N more" are set in `_pipeline/labels.yml`.

Each plot type can also have a `caption` there: one line explaining the metric, shown under the plot once the options stack (and dropped when `image=` replaces the plot). The first slide of each plot type is preceded by a question slide, an eyebrow naming the metric over the question it helps answer (see `#q-knn-purity` in `slides/pipeline_knn.qmd`).

**Tool logos.** Each stage can show the tools it is built on: a row of small logos under its options, revealed with the stage and faded out with the rest of the diagram once the options stack. The `tools:` catalog at the bottom of `_pipeline/labels.yml` names each tool once: `name`, `logo` in `images/tools/` (or `logo: null` for a text badge), and optionally `pill: true` for a light background behind a dark logo, a `caption` shown under the logo instead of the name, and an `option` tying the tool to one pipeline option (an id such as `generate:alphaearth`), so the logo lights up when the path reaches that option and hangs under it once the options stack. Each stage lists the catalog keys it uses under `tools:`; a stage without them draws no row, and several tools can share an `option` (Zarr and Source Cooperative both sit under AlphaEarth). A slide can also add `tools=pmtiles,s3` to the shortcode to draw a row of catalog tools under the plot or image once the options stack, for tools that come after the pipeline (see `#app-pipeline` in `slides/app.qmd`). The catalog is kept to the cloud-native pieces (STAC, xarray, Dask, Zarr, Source Cooperative, PMTiles, S3) and can be extended by adding an entry and a logo. `pixi run sync` copies the catalog into the data files (and to `_pipeline/data/tools.json`) and checks that every logo exists; where each logo came from is recorded in `images/tools/SOURCES.md`.

## Config panels

`{{< config ... >}}` shows lines of a real config as a panel, and can step through them in time with the slide's text (see `#lc-datagen` in `slides/lc-dataset.qmd`, and `slides/lc-configs.qmd`):

```markdown
::: {.two-col .cfg-cols}
::: {}
- [Sentinel-2 L2A: 4 scenes / year]{cfg="s2l2a"}
- [960 m chips]{cfg="chips"}
:::

{{< config datagen s2l2a chips size=18 >}}
:::
```

- **Excerpts:** the first argument names an excerpt in `_pipeline/excerpts.yml`: a file in gelos-lc or gelos-lc-datagen, and named regions, each a list of keys to show. `pixi run sync` cuts those lines out of the file, so a panel can't drift from the config. The text is the file's own, apart from what the top of `_pipeline/excerpt.py` lists (dropped comments and blank lines, lists reflowed onto one line); lines left out between regions are marked by a small gap.
- **Steps:** each argument after the name adds a click that lights up one region, or several joined with `+`. With none, the panel is static.
- **Tied text:** a span with `cfg="<region>"` (or several regions, separated by spaces) is lit along with its region and dimmed while another one is.
- **Layout:** `.two-col .cfg-cols` puts text beside a panel, the panel taking the width of its longest line; `.cfg-chain` puts several panels side by side with an arrow between them. `size=<px>` sets a panel's font size.

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

Clips are muted, loop, and restart whenever their slide is shown. `pixi run clips` speeds them up by the factor in `_pipeline/clips.yml` (default 2×, with per-clip overrides); editing that file re-encodes every clip. A recording that is too long for one slide can also be cut into several clips: list it under `parts` in `clips.yml`, each part with the name of the clip it writes and where it starts and ends in the recording (in seconds, before the speed-up). The whole recording is still written as well.

When a deck opens, `pipeline.js` downloads every clip in deck order and plays each from its local copy, so a slow conference connection can't stall one mid-slide. A counter at the bottom left (`loading clips 3 / 8`) shows the download; on a timed deck, wait on the title slide until it reads `clips ready` and fades. A clip that fails to download keeps its URL and streams as before, and the counter says so.

## Grid-alignment figure

`{{< grid-alignment >}}` (see `slides/chip-size.qmd`) shows why chips are 960 m on a side: the pixel grids of each band stack up, each is cut into 16 × 16 px patches, then candidate chip sizes are tried: 160, 320 and 640 m leave Landsat with part-patches, and 960 m (2 × lcm(160, 480)) is the first size past 640 m that tiles both bands. It is one inline SVG with a click per step.

- **Geometry, text and steps:** `_grid/make_grid_figure.py`, with `CHIP_CANDIDATES`, `PATCH` and `BANDS` at the top. Run `pixi run grid-figure` and commit `_grid/grid-alignment.svg`; never edit the SVG by hand.
- **Colour and timing:** `_grid/grid-alignment.css`, with the durations as custom properties at the top.
- **Skipping the build:** `{{< grid-alignment start=patches >}}` opens with the pixel and patch grids already drawn, leaving only the clicks that try each candidate chip (`start=grids` opens with just the pixel grids). `slides/chip-size-short.qmd` uses it for timed decks, with `data-autoslide` on the slide setting how long each step is held (see "Timed decks").

## Extraction figure

`{{< extraction >}}` (see `slides/lc-dataset.qmd`) shows how embeddings are pulled out of a model: a chip's images at four seasons are cut into patches and go into the model, one token per patch per season comes out, then each extraction strategy keeps some of those tokens. It is one inline SVG with a click per step: patches, tokens, then one per strategy.

- **Model, inputs and strategies:** read from one gelos-lc config, named by `CONFIG` at the top of `_extraction/make_extraction_figure.py`. The sensors under its `data.init_args.bands` go into the model and the others dim; each strategy's `slice_args` are applied to the token sequence as gelos applies them, so the figure highlights what the config selects. The run prints which season and patches each strategy keeps.
- **Chips:** `CHIP_ID` picks the chip. Its GeoTIFFs are downloaded from the open `gelos-fm` bucket into `_extraction/cache/` (not committed) and rendered to `images/lc-dataset/chips/`. Token colours are the mean colour of each token's Sentinel-2 patch.
- **Regenerating:** run `pixi run extraction-figure` (expects gelos-lc next to this repo; otherwise add `--gelos-lc <path>`) and commit `_extraction/extraction.svg` and `images/lc-dataset/chips/`; never edit the SVG by hand. A model not yet listed in `PATCH` needs its patch size added there.
- **Colour and timing:** `_extraction/extraction.css`, with the durations as custom properties at the top.

## Land Cover figures

`{{< lc-figure map >}}` and `{{< lc-figure classes >}}` (see `slides/lc-dataset.qmd`) show the dataset: a world map of where the chips are, and a bar chart of how many there are of each land cover class. Both are static inline SVGs drawn from the same table, so they agree.

- **Data:** the chip centroids that gelos-lc-datagen publishes for the GELOS app (`pmtiles/centroids.pmtiles` in the open `gelos-fm` bucket: one point per chip, with its class), downloaded into `_lc-figures/cache/` (not committed) along with the Natural Earth 1:110m land polygons. The run prints the chip count per class and the total.
- **Map:** Equal Earth, cut off at 60° S. Chips are counted in 1° cells and each occupied cell is one dot at the mean position of its chips, with an area that grows with the count; `CELL`, `DOT_MIN` and `DOT_MAX` at the top of `_lc-figures/make_lc_figures.py` set this.
- **Regenerating:** run `pixi run lc-figures` and commit `_lc-figures/chip-map.svg` and `_lc-figures/class-distribution.svg`; never edit the SVGs by hand.
- **Colour and type:** `_lc-figures/lc-figures.css`, except the bars, which are filled with each class's colour from the chip table (the colour the GELOS app draws it in).

## Timed decks

`cng-lightning.qmd` follows the organizers' [template](https://github.com/cloudnativegeo/lightning-talk-quarto-TEMPLATE): a title slide, exactly 20 content slides that auto-advance every 15 s (the CNG format sets `auto-slide: 15000`), and a closing slide. Reveal times every fragment of a slide separately, so a slide with five clicks at the default would take 90 s. A slide with clicks therefore sets its own pace so that its states add up to 15 s, and the deck's front matter lists the 20 slides with their timing:

- **Per slide:** `data-autoslide="2500"` on the slide heading holds each of its states (the slide, then each fragment) for 2.5 s: six states in 15 s. The title and thanks slides set `0`, so they wait for a click.
- **Per fragment:** a fragment with its own `data-autoslide` overrides the slide's (the slide's own time still holds its opening state). The pipeline shortcode writes one with `hold=`, so the stages can be drawn fast and the plots held longer: `data-autoslide="1200"` with `hold=3000` draws five stages in 6 s and holds the path, the config and the plot for 9 s.
- **Clips:** keep every clip shorter than 15 s, so it plays once (or loops) and the slide moves on with the rest (`ffprobe videos/<name>.mp4` prints the duration). A longer recording is cut into parts in `_pipeline/clips.yml`, one slide each. Reveal would otherwise stretch a fragment-less slide to fit its video, and the deck would run long.
- **Timed reveals** (`.a-fade`, `.a-rise` with `--d`) are CSS, not fragments, so they don't add states: use them for slides that should move while holding one state.
- **Variants:** a slide file that needs timing (or a shorter telling) gets a `-short.qmd` twin in `slides/` with its own ids (`chip-size-short.qmd`, `app-short.qmd`, ...), and the deck includes the twin. The twin's body is a copy: when the facts change in the shared file, change them there too. Adding a slide to the CNG deck means dropping another: the organizers ask for the template's 20.
- **Countdown bar:** `countdown.html` in the house style restarts the bar on every fragment and reads the fragment's or slide's time. With auto-slide off (an untimed deck, or `?autoSlide=0`) it also strips every `data-autoslide`, so timed slides wait for a click like the others.

## Preview and publish

```bash
quarto preview full.qmd
```

For auto-advancing decks, add `?autoSlide=0` before the `#` in the preview URL to stop auto-advance while editing (this stops the slides with their own `data-autoslide` too).

Pushing to `main` renders every deck and publishes `_site/` to the `gh-pages` branch. Enable Pages once under **Settings → Pages → Deploy from branch → gh-pages**. Decks are then at `https://dwgodwin.github.io/gelos-talks/<deck>.html`.

Both themes come from [quarto-slides-template](https://github.com/DWGodwin/quarto-slides-template); don't edit `_extensions/` here. To update them: `quarto add DWGodwin/quarto-slides-template`.
