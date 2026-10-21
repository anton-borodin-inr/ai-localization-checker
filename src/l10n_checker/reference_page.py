"""Self-contained local review UI. Approval requires an explicit user action."""

import base64
import html
from pathlib import Path


def render_page(candidate: dict, data: bytes) -> str:
    title = html.escape(candidate["screen"] + " / " + candidate["language"])
    image = html.escape(candidate["image"]["file"], quote=True)
    width, height = candidate["image"]["size"]
    encoded = base64.b64encode(data).decode("ascii")
    script = Path(__file__).with_name("reference_review.js").read_text(encoding="utf-8")
    return f'''<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Candidate review — {title}</title>
<style>
*{{box-sizing:border-box}}body{{margin:0;background:#f5f6f8;color:#17202a;font:15px system-ui,sans-serif}}
header{{padding:18px 24px;background:#172536;color:white}}h1{{font-size:22px;margin:0 0 8px}}
header p{{margin:6px 0;max-width:1000px}}button,input,select,textarea{{font:inherit}}
button{{cursor:pointer;padding:8px 12px;border:1px solid #b7c2cc;border-radius:6px;background:white}}
button:disabled{{opacity:.5;cursor:default}}#confirm{{background:#2455a4;color:white;border:0}}
.controls{{position:sticky;top:0;z-index:5;background:white;padding:12px 24px;border-bottom:1px solid #ccd4dc;display:flex;gap:12px;flex-wrap:wrap;align-items:center}}
.workspace{{display:grid;grid-template-columns:minmax(0,1.6fr) minmax(360px,1fr);gap:18px;padding:18px}}
.picture{{position:sticky;top:135px;align-self:start;background:#101820;border-radius:8px;overflow:auto;max-height:calc(100vh - 165px)}}
.canvas{{position:relative;width:100%;min-width:100%}}
.picture img{{width:100%;display:block}}svg{{position:absolute;inset:0;width:100%;height:100%;pointer-events:none}}
.row{{background:white;border:1px solid #d5dde5;border-left:5px solid #426ea5;border-radius:7px;margin-bottom:12px;padding:12px}}
.row.diagnostic{{border-left-color:#b76c12}}.row.selected{{outline:3px solid #2e70d1}}
textarea{{width:100%;min-height:55px;resize:vertical;margin:8px 0}}.row label{{display:inline-flex;align-items:center;gap:5px;margin:4px 8px 4px 0}}
.meta{{font-size:12px;color:#52616e;overflow-wrap:anywhere}}.warning{{color:#885005;margin:6px 0}}
details{{margin-top:8px}}pre{{white-space:pre-wrap;overflow-wrap:anywhere}}#message{{color:#8c3f00;padding:0 24px}}
@media(max-width:1000px){{.workspace{{grid-template-columns:1fr}}.picture{{position:relative;top:0}}}}
</style><header><h1>{title}</h1>
<p>Engine text candidate · requires Anton's confirmation · no OCR/model output · no defect labels</p>
<p>Check text and boxes against the image. Hidden full input is provenance only. Review clipping and uncertain units explicitly.</p></header>
<div class="controls"><button id="start">Start review</button><button id="pause" disabled>Pause</button>
<span id="timer">Not started</span><button id="add">Add unit</button>
<label><input type="checkbox" id="glyphs" checked>Glyph boxes</label>
<label><input type="checkbox" id="owners">Owner boxes</label>
<label><input type="checkbox" id="clips">Clip boxes</label>
<label>Image zoom <select id="zoom"><option value="1">Fit</option><option value="2">2×</option><option value="3">3×</option></select></label>
<label><input type="checkbox" id="ack">I am Anton and have reviewed this screen</label>
<button id="confirm" disabled>Confirm and export</button></div>
<p id="message" role="status"></p><main class="workspace">
<div class="picture"><div class="canvas" id="canvas"><img src="{image}" alt="Original captured screenshot">
<svg id="overlay" viewBox="0 0 {width} {height}"></svg></div></div>
<section><p id="counts"></p><div id="rows"></div></section></main>
<script>globalThis.originalBase64="{encoded}";</script><script>{script}</script></html>'''
