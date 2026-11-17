#!/usr/bin/env python3
"""Build a LinkedIn PDF carousel (1080x1350 pages) from a JSON spec.

Usage: python3 build_carousel.py spec.json out_dir

Spec format:
{
  "name": "file-stem",
  "accent": "#F5B83D",
  "series": "Malware traffic analysis",
  "footer": "Vlad Guliakin  ·  github.com/dancemonk/...",
  "base_dir": "/path/screenshots/are/relative/to",
  "style": "terminal",           (optional; default "classic")
  "title": "PDF document title",  (optional)
  "prompt": "malware",            (terminal style: vlad@soc:~/<prompt>$ <series>)
  "slides": [
    {"type": "cover", "kicker": "...", "title": "...", "sub": "...", "ascii": "SCOPE"},
    {"type": "step", "cmd": "statistics → conversations", "title": "...", "body": ["line"],
     "image": "rel/path.png", "window": "wireshark · conversations", "caption": "..."},
    {"type": "text", "title": "...", "bullets": ["...", "..."]},
    {"type": "end", "title": "...", "body": ["..."], "link": "github.com/..."}
  ]
}
Output: out_dir/<name>.pdf and out_dir/<name>-NN.png per slide.
"""
import base64, html, json, mimetypes, pathlib, sys
from playwright.sync_api import sync_playwright

W, H = 1080, 1350


FRAME_W = 900  # inner width of the screenshot frame on a 1080 slide


def img_data(path, crops=None):
    """Return a data URI. Optional crops [[x0,y0,x1,y1], ...] (original pixels) are
    stacked top to bottom at one shared scale, with a gray line at each cut, then the
    result is scaled to the frame width so small evidence becomes readable."""
    import io
    from PIL import Image, ImageDraw
    im = Image.open(path).convert("RGB")
    parts = [im.crop(tuple(c)) for c in crops] if crops else [im]
    gap = 10
    w = max(p.width for p in parts)
    h = sum(p.height for p in parts) + gap * (len(parts) - 1)
    comp = Image.new("RGB", (w, h), "white")
    y = 0
    d = ImageDraw.Draw(comp)
    for i, p in enumerate(parts):
        comp.paste(p, (0, y)); y += p.height
        if i < len(parts) - 1:
            d.rectangle([0, y + gap // 2 - 1, w, y + gap // 2 + 1], fill=(170, 170, 170)); y += gap
    scale = (FRAME_W * 2) / comp.width  # 2x for sharp text
    comp = comp.resize((FRAME_W * 2, round(comp.height * scale)), Image.LANCZOS)
    buf = io.BytesIO(); comp.save(buf, "PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def inline(text):
    """Escape, then allow `code` spans and **bold**."""
    t = html.escape(text)
    out, code = [], False
    for part in t.split("`"):
        out.append(f"<code>{part}</code>" if code else part)
        code = not code
    t = "".join(out)
    while "**" in t:
        t = t.replace("**", "<b>", 1).replace("**", "</b>", 1)
    return t.replace("\n", "<br>")


CSS = """
@page { size: 1080px 1350px; margin: 0 }
* { box-sizing: border-box; margin: 0; padding: 0 }
html, body { width: 1080px; height: 1350px; background: #101317 }
body { font-family: 'Inter', sans-serif; color: #EEF0F2; -webkit-font-smoothing: antialiased }
.slide { position: relative; width: 1080px; height: 1350px; padding: 84px 80px 0; display: flex; flex-direction: column; overflow: hidden }
.top { display: flex; justify-content: space-between; align-items: center; font-size: 24px; color: #8B939C; letter-spacing: .02em; margin-bottom: 44px }
.top .series { color: var(--accent); font-weight: 600; text-transform: uppercase; letter-spacing: .12em; font-size: 22px }
h1 { font-family: 'Inter Display', 'Inter', sans-serif; font-weight: 700; font-size: 56px; line-height: 1.12; letter-spacing: -.015em; margin-bottom: 28px }
.body p { font-size: 32px; line-height: 1.4; color: #C9CED4; margin-bottom: 14px }
.body p b, li b { color: #FFFFFF }
code { font-family: 'DejaVu Sans Mono', monospace; font-size: .86em; background: #1D232A; color: var(--accent); padding: 2px 9px; border-radius: 6px }
.shot { margin-top: 26px; flex: 1; min-height: 0; display: flex; flex-direction: column; justify-content: center; padding-bottom: 20px }
.frame { background: #FFFFFF; border-radius: 14px; padding: 10px; box-shadow: 0 0 0 2px #262D35; display: flex; justify-content: center; align-items: center; overflow: hidden; max-height: 100% }
.frame img { width: 100%; max-height: 100%; object-fit: contain; object-position: left top; display: block }
.note { font-size: 28px; line-height: 1.4; color: #C9CED4; margin-top: 18px }
.caption { font-size: 22px; color: #8B939C; margin-top: 14px; line-height: 1.35 }
ul { list-style: none; margin-top: 8px }
li { font-size: 32px; line-height: 1.38; color: #C9CED4; padding-left: 40px; position: relative; margin-bottom: 22px }
li:before { content: ''; position: absolute; left: 0; top: 17px; width: 16px; height: 4px; background: var(--accent); border-radius: 2px }
.foot { height: 110px; flex: none; display: flex; align-items: center; justify-content: space-between; font-size: 22px; color: #6E7781; border-top: 2px solid #1E242B; margin-top: 30px }
.cover { justify-content: center; padding-bottom: 110px }
.cover .kicker { color: var(--accent); font-weight: 600; font-size: 28px; letter-spacing: .12em; text-transform: uppercase; margin-bottom: 36px }
.cover h1 { font-size: 92px; line-height: 1.04; letter-spacing: -.025em; margin-bottom: 40px }
.cover .sub { font-size: 36px; line-height: 1.4; color: #C9CED4; max-width: 880px }
.cover .bar { width: 120px; height: 8px; background: var(--accent); border-radius: 4px; margin-bottom: 44px }
.cover .swipe { position: absolute; right: 80px; bottom: 150px; font-size: 26px; color: var(--accent); font-weight: 600 }
.cover .foot { position: absolute; left: 80px; right: 80px; bottom: 0 }
.end .link { margin-top: 30px; font-family: 'DejaVu Sans Mono', monospace; font-size: 30px; color: var(--accent); word-break: break-all }
"""


TERM_CSS = """
.mono, .top, .foot, .cmd, .cover .kicker, .cover .swipe, .caption { font-family: 'DejaVu Sans Mono', monospace }
.top { font-size: 22px; letter-spacing: 0; color: #8B939C }
.top .who { color: var(--accent) }
.cmd { color: var(--accent); font-size: 26px; margin-bottom: 18px }
.foot { font-size: 20px }
.frame { background: #0D1014; padding: 0; border-radius: 14px; box-shadow: 0 0 0 2px #2A2F36; flex-direction: column; align-items: stretch }
.frame .tb { height: 44px; flex: none; display: flex; align-items: center; gap: 10px; padding: 0 18px; border-bottom: 2px solid #2A2F36; font: 19px 'DejaVu Sans Mono', monospace; color: #6E7781 }
.frame .tb i { width: 13px; height: 13px; border-radius: 50%; background: #2F353D }
.frame .tb span { margin-left: 8px }
.frame .pic { background: #FFFFFF; padding: 10px; min-height: 0; display: flex }
li:before { content: '>'; background: none; width: auto; height: auto; top: 0; color: var(--accent); font: 30px/1.38 'DejaVu Sans Mono', monospace }
.cover pre { font-family: 'DejaVu Sans Mono', monospace; color: var(--accent); line-height: 1.0; margin-bottom: 44px }
.cover .kicker { text-transform: none; letter-spacing: 0; font-weight: 400; font-size: 28px }
.cover .swipe { font-weight: 400 }
.top { position: absolute; top: 84px; left: 80px; right: 80px; margin: 0 }
.slide { padding-top: 190px; padding-bottom: 140px }
.slide > .foot { position: absolute; left: 80px; right: 80px; bottom: 0; margin: 0 }
.slide.text, .slide.end { justify-content: center }
.slide.text .sp, .slide.end .sp { display: none }
.slide.text h1, .slide.end h1 { font-size: 68px; margin-bottom: 40px }
.slide.text li { font-size: 38px; margin-bottom: 30px }
.slide.end .body p { font-size: 38px }
.slide.end .link { font-size: 32px; margin-top: 40px }
.slide.step .shot { justify-content: flex-start; margin-top: 44px }
.slide.text.dense h1 { font-size: 60px; margin-bottom: 30px }
.slide.text.dense li { font-size: 31px; line-height: 1.34; margin-bottom: 20px }
.rows { margin-top: 8px; border-top: 2px solid #232A32 }
.row { display: grid; grid-template-columns: 300px 1fr; gap: 28px; align-items: center; padding: 16px 0; border-bottom: 2px solid #232A32 }
.row .k { font-family: 'DejaVu Sans Mono', monospace; font-size: 34px; font-weight: 700; color: var(--accent); line-height: 1.2 }
.row .v { font-size: 30px; line-height: 1.3; color: #E6E9ED }
.row .v small { display: block; font-size: 24px; color: #8B939C; margin-top: 4px }
.rows.wide .row { grid-template-columns: 380px 1fr }
.slide.text.card h1 { font-size: 72px; line-height: 1.05; margin-bottom: 34px }
.slide .tail { font-size: 26px; line-height: 1.4; color: #8B939C; margin-top: 26px }
"""


def ascii_banner(text):
    import pyfiglet
    art = pyfiglet.figlet_format(text, font="ansi_shadow").rstrip("\n")
    cols = max(len(l) for l in art.splitlines())
    fs = min(34, 920 / (cols * 0.602))
    return f'<pre style="font-size:{fs:.1f}px">{html.escape(art)}</pre>'


def page(spec, s, i, n):
    acc = spec.get("accent", "#F5B83D")
    term = spec.get("style") == "terminal"
    if term:
        top = (f'<div class="top"><span><span class="who">vlad@soc</span>:~/{html.escape(spec.get("prompt", ""))}$ '
               f'{inline(spec["series"])}</span><span>{i:02d}/{n:02d}</span></div>')
    else:
        top = (f'<div class="top"><span class="series">{inline(spec["series"])}</span>'
               f'<span>{i}/{n}</span></div>')
    foot = f'<div class="foot"><span>{inline(spec["footer"])}</span></div>'
    t = s.get("type", "step")
    if t == "cover":
        if term:
            inner = (f'<div class="slide cover">' + top.replace('class="top"', 'class="top" style="position:absolute;top:84px;left:80px;right:80px"') +
                     (ascii_banner(s["ascii"]) if s.get("ascii") else '<div class="bar"></div>') +
                     f'<div class="kicker">$ {inline(s.get("kicker", ""))}</div>'
                     f'<h1>{inline(s["title"])}</h1><div class="sub">{inline(s.get("sub", ""))}</div>'
                     f'<div class="swipe">swipe &rarr;</div>{foot}</div>')
        else:
          inner = (f'<div class="slide cover"><div class="bar"></div>'
                 f'<div class="kicker">{inline(s.get("kicker", ""))}</div>'
                 f'<h1>{inline(s["title"])}</h1><div class="sub">{inline(s.get("sub", ""))}</div>'
                 f'<div class="swipe">Swipe &rarr;</div>{foot}</div>')
    else:
        dense = (" dense" if s.get("dense") else "") + (" card" if s.get("rows") else "")
        parts = [f'<div class="slide {t}{dense}">', top]
        if s.get("cmd"):
            parts.append(f'<div class="cmd">$ {inline(s["cmd"])}</div>')
        parts.append(f'<h1>{inline(s["title"])}</h1>')
        if s.get("body"):
            parts.append('<div class="body">' + "".join(f"<p>{inline(p)}</p>" for p in s["body"]) + "</div>")
        if s.get("rows"):
            wide = " wide" if s.get("wide") else ""
            parts.append(f'<div class="rows{wide}">' + "".join(
                f'<div class="row"><div class="k">{inline(r[0])}</div><div class="v">{inline(r[1])}'
                + (f'<small>{inline(r[2])}</small>' if len(r) > 2 else '') + '</div></div>' for r in s["rows"]) + "</div>")
        if s.get("tail"):
            parts.append(f'<div class="tail">{inline(s["tail"])}</div>')
        if s.get("bullets"):
            parts.append("<ul>" + "".join(f"<li>{inline(b)}</li>" for b in s["bullets"]) + "</ul>")
        if s.get("note"):
            parts.append(f'<div class="note">{inline(s["note"])}</div>')
        if s.get("link"):
            parts.append(f'<div class="link">{html.escape(s["link"])}</div>')
        if s.get("image"):
            base = pathlib.Path(spec["base_dir"]).expanduser()
            if not base.is_absolute():  # relative = inside the folder that holds your repos
                import os
                repos = os.environ.get("REPOS_DIR") or pathlib.Path(__file__).resolve().parents[2]
                base = pathlib.Path(repos) / base
            src = img_data(base / s["image"], s.get("crops"))
            cap = f'<div class="caption">{inline(s["caption"])}</div>' if s.get("caption") else ""
            if term:
                tb = f'<div class="tb"><i></i><i></i><i></i><span>{html.escape(s.get("window", ""))}</span></div>'
                parts.append(f'<div class="shot"><div class="frame">{tb}<div class="pic"><img src="{src}"></div></div>{cap}</div>')
            else:
                parts.append(f'<div class="shot"><div class="frame"><img src="{src}"></div>{cap}</div>')
        else:
            parts.append('<div class="sp" style="flex:1"></div>')
        parts.append(foot + "</div>")
        inner = "".join(parts)
    title = html.escape(spec.get("title") or spec["name"])
    css = CSS + (TERM_CSS if term else "")
    return f"<!doctype html><html><head><meta charset='utf-8'><title>{title}</title><style>:root{{--accent:{acc}}}{css}</style></head><body>{inner}</body></html>"


def main(spec_path, out_dir):
    spec = json.loads(pathlib.Path(spec_path).read_text())
    out = pathlib.Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    slides = spec["slides"]; n = len(slides)
    pages = [page(spec, s, i + 1, n) for i, s in enumerate(slides)]
    full = pages[0].split("<body>")[0] + "<body>" + "".join(p.split("<body>")[1].split("</body>")[0] for p in pages) + "</body></html>"
    with sync_playwright() as p:
        import os, shutil
        chrome = next((c for c in [os.environ.get("CHROME_PATH"), shutil.which("google-chrome"),
                                   shutil.which("chromium"), shutil.which("chromium-browser"),
                                   "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"]
                       if c and os.path.exists(c)), None)
        b = p.chromium.launch(executable_path=chrome, args=["--no-sandbox"]) if chrome else p.chromium.launch()
        pg = b.new_page(viewport={"width": W, "height": H})
        for i, h in enumerate(pages, 1):
            pg.set_content(h, wait_until="networkidle")
            # flag text overflow so a slide never cuts off silently
            over = pg.evaluate("() => { const s=document.querySelector('.slide'); return s.scrollHeight > s.clientHeight + 2 }")
            if over:
                print(f"WARNING: slide {i} overflows", file=sys.stderr)
            pg.screenshot(path=str(out / f"{spec['name']}-{i:02d}.png"))
        pg.set_content(full, wait_until="networkidle")
        pg.pdf(path=str(out / f"{spec['name']}.pdf"), width=f"{W}px", height=f"{H}px",
               print_background=True, prefer_css_page_size=True)
        b.close()
    print(out / f"{spec['name']}.pdf")


if __name__ == "__main__":
    main(*sys.argv[1:3])
