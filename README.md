# GELOS talks

Slides about [GELOS](https://github.com/ClarkCGA/gelos), built with [Quarto RevealJS](https://quarto.org/docs/presentations/revealjs/).

## Layout

```
full.qmd             master deck: every slide file
cng-lightning.qmd    CNG lightning talk (5 min, auto-advancing)
index.qmd            landing page linking all decks
slides/              slide files; decks include these, they never render alone
images/              figures used by slides
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

## Preview and publish

```bash
quarto preview full.qmd
```

For auto-advancing decks, add `?autoSlide=0` before the `#` in the preview URL to stop auto-advance while editing.

Pushing to `main` renders every deck and publishes `_site/` to the `gh-pages` branch. Enable Pages once under **Settings → Pages → Deploy from branch → gh-pages**. Decks are then at `https://dwgodwin.github.io/gelos-talks/<deck>.html`.

Both themes come from [quarto-slides-template](https://github.com/DWGodwin/quarto-slides-template); don't edit `_extensions/` here. To update them: `quarto add DWGodwin/quarto-slides-template`.
