# LinkedIn carousel builder

Turns a JSON spec and your screenshots into a LinkedIn PDF carousel (1080x1350 pages) plus one PNG per slide.

## Use it

```bash
pip install playwright pillow --break-system-packages   # or in a venv
python3 -m playwright install chromium                   # skip if Chrome is installed
cd ~/Projects/linkedin-media
python3 tools/build_carousel.py tools/specs/mta-first-to-last.json 2026-11-mta-first-to-last
```

Output: `<name>.pdf` and `<name>-01.png` ... in the folder you name. Rename them to `carousel.pdf` and `cover.png` (slide 1), delete the other PNGs, commit and push. GitHub Pages then serves them at `https://dancemonk.github.io/linkedin-media/<folder>/`.

On Fedora, change `executable_path` in `build_carousel.py` to your Chrome or Chromium path, or delete it to use Playwright's own browser.

## Spec

| Field | What it does |
|---|---|
| `name` | File name of the output |
| `accent` | One accent color per series (malware `#F5B83D`, SIEM `#5EC8E5`) |
| `series`, `footer` | Small label at the top, name and repo at the bottom |
| `base_dir` | Folder the `image` paths are relative to. A relative path starts from the folder that holds your repos (the parent of `linkedin-media`, or `$REPOS_DIR`). |
| `slides[]` | `cover`, `step` (default), `text` or `end` |

Slide fields: `title`, `body` (paragraphs), `bullets`, `note`, `link`, `image`, `crops`, `caption`.
Use `` `code` `` and `**bold**` inside text.

`crops` is a list of `[x0, y0, x1, y1]` boxes in the screenshot's own pixels. They are stacked top to bottom with a gray line at each cut (the same convention as the repo screenshots) and scaled to the slide width. Crop to the filter bar, the 2-3 columns that matter, and the "Displayed" count. A full-width Splunk or Wireshark screenshot is unreadable on a phone.

## Rules for every carousel

- 8-12 slides, one idea per slide, under 60 words.
- Every number and claim comes from the published case file. No new analysis on slides.
- Indicators in slide text are defanged (`23.22.63[.]114`, `hxxp://`). Screenshots keep raw values, as in the repos.
- Redact with solid boxes before capture, never blur. No employer data, ever.
- The script prints `WARNING: slide N overflows` if text is cut. Shorten the text, don't shrink the font.
