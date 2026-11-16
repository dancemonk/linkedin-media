# LinkedIn carousel builder

Turns a JSON spec and screenshots from my case repos into a LinkedIn PDF carousel (1080x1350 pages).

## Automatic build (normal way)

1. Add a spec to `tools/specs/` with a `folder` name (for example `2026-12-case02`) and push.
2. The GitHub Action `Build carousels` builds `<folder>/carousel.pdf` and `<folder>/cover.png`, commits them and asks GitHub Pages to publish.
3. A minute later they are live at `https://dancemonk.github.io/linkedin-media/<folder>/carousel.pdf` and `.../cover.png`.

The Action builds a spec only when its folder has no `carousel.pdf` yet, so a published carousel is never changed by accident. To rebuild one on purpose, add `"rebuild": true` to its spec and push. The Action removes the flag after the build. A slide whose text overflows fails the build.

## Local build (to preview)

```bash
cd ~/Projects/linkedin-media
uv run --with playwright --with pillow python tools/build_carousel.py tools/specs/<spec>.json preview
```

The case repos must sit next to `linkedin-media` (or set `REPOS_DIR`). Delete the `preview` folder after; don't commit it.

## Spec

| Field | What it does |
|---|---|
| `name` | File name of the build output |
| `folder` | Output folder in this repo, `YYYY-MM-topic` |
| `rebuild` | Optional. `true` forces one rebuild of an existing folder |
| `accent` | One accent color per series (malware `#F5B83D`, SIEM `#5EC8E5`) |
| `style` | `terminal` for the terminal look (prompt bar, `$ command` labels, screenshots in a terminal window). Leave it out for the original style. |
| `prompt` | Terminal style: the folder shown in `vlad@soc:~/<prompt>$` |
| `title` | Title saved inside the PDF |
| slide `ascii` | Cover only, terminal style: a short word shown as an ASCII banner |
| slide `cmd` | Terminal style: the `$ ...` label above a slide title |
| slide `window` | Terminal style: the label in the screenshot window bar |
| `series`, `footer` | Small label at the top, name and repo at the bottom |
| `base_dir` | Screenshot folder, starting with the case repo name (for example `siem-splunk-lab`) |
| `slides[]` | `cover`, `step` (default), `text` or `end` |

Slide fields: `title`, `body` (paragraphs), `bullets`, `note`, `link`, `image`, `crops`, `caption`.
Use `` `code` `` and `**bold**` inside text.

`crops` is a list of `[x0, y0, x1, y1]` boxes in the screenshot's own pixels. They are stacked top to bottom with a gray line at each cut and scaled to the slide width. Crop to the filter bar, the 2-3 columns that matter, and the result count. A full-width Splunk or Wireshark screenshot is unreadable on a phone.

## Rules for every carousel

- 8-12 slides, one idea per slide, under 60 words.
- Every number and claim comes from the published case file. No new analysis on slides.
- Indicators in slide text are defanged (`23.22.63[.]114`, `hxxp://`).
- Redact with solid boxes before capture, never blur. No employer data.
- Screenshots must be in a public case repo, because the Action can only read public repos.
