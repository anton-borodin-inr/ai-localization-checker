"""Self-contained local HTML review page for Stage 3 dev labels (D-062)."""

import html
import json
from pathlib import Path


def _safe_inline_json(value: dict) -> str:
    return (
        json.dumps(value, ensure_ascii=False, allow_nan=False)
        .replace("</", "<\\/")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


def render_page(drafts_payload: dict) -> str:
    """Render one self-contained HTML file with inline CSS, JS and drafts JSON."""
    run_id = html.escape(drafts_payload.get("run_id") or "dev")
    total = len(drafts_payload.get("screenshots") or [])
    inline_data = _safe_inline_json(drafts_payload)
    script = Path(__file__).with_name("label_review.js").read_text(encoding="utf-8")
    return f"""<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Stage 3 label review — {run_id}</title>
<style>
*{{box-sizing:border-box}}
body{{margin:0;background:#f4f6f8;color:#17202a;font:14px/1.4 system-ui,-apple-system,sans-serif}}
header{{padding:12px 18px;background:#172536;color:#fff;display:flex;flex-wrap:wrap;gap:12px;align-items:center;justify-content:space-between}}
header h1{{font-size:18px;margin:0}}
.sub{{font-size:12px;color:#c7d4e2}}
.bar{{position:sticky;top:0;z-index:10;background:#fff;border-bottom:1px solid #cdd6df;padding:8px 18px;display:flex;flex-wrap:wrap;gap:8px;align-items:center}}
button,select,input,textarea{{font:inherit}}
button{{cursor:pointer;padding:6px 10px;border:1px solid #b4c0cc;border-radius:5px;background:#fff;color:#17202a}}
button:hover:not(:disabled){{background:#eef3f8}}
button:disabled{{opacity:.5;cursor:default}}
button.primary{{background:#2455a4;color:#fff;border-color:#2455a4}}
button.primary:hover:not(:disabled){{background:#1d468a}}
button.ok{{background:#1c7c4a;color:#fff;border-color:#1c7c4a}}
button.ok:hover:not(:disabled){{background:#15623a}}
button.danger{{color:#a61b1b;border-color:#e0b4b4}}
button.active{{background:#172536;color:#fff;border-color:#172536}}
.progress-wrap{{display:flex;align-items:center;gap:8px}}
progress{{width:130px;height:14px}}
.filters{{display:flex;gap:4px;flex-wrap:wrap}}
.spacer{{flex:1}}
#status{{margin:0;padding:6px 18px;font-size:13px;color:#8c3f00;min-height:26px}}
.workspace{{display:grid;grid-template-columns:minmax(0,1.7fr) minmax(370px,1fr);gap:14px;padding:0 18px 18px}}
.viewer-col{{display:flex;flex-direction:column;gap:8px;min-width:0}}
.viewer-tools{{display:flex;flex-wrap:wrap;gap:10px;align-items:center;font-size:13px}}
.picture{{background:#101820;border-radius:6px;overflow:auto;max-height:calc(100vh - 185px);border:1px solid #2c3e50}}
.canvas{{position:relative;width:100%}}
.canvas img{{display:block;width:100%;height:auto}}
.canvas svg{{position:absolute;inset:0;width:100%;height:100%}}
.canvas svg rect.box{{cursor:pointer}}
.panel{{display:flex;flex-direction:column;gap:10px;min-width:0}}
.screen-head{{background:#fff;border:1px solid #d5dde5;border-radius:6px;padding:10px 12px}}
.screen-head h2{{margin:0 0 4px;font-size:15px;overflow-wrap:anywhere}}
.badge{{display:inline-block;padding:2px 7px;border-radius:999px;font-size:12px;font-weight:600;margin-right:6px}}
.badge.reviewed{{background:#d7f3e3;color:#145a32}}
.badge.pending{{background:#fdebd0;color:#7e5109}}
.badge.clean{{background:#e8eef5;color:#2c3e50}}
.badge.mutation{{background:#e8e3fa;color:#4a235a}}
.flags{{background:#fff8e6;border:1px solid #e6c665;border-radius:6px;padding:10px 12px;font-size:12px}}
.flags pre{{margin:6px 0 0;white-space:pre-wrap;overflow-wrap:anywhere;font:12px/1.35 ui-monospace,monospace}}
.actions-row{{display:flex;flex-wrap:wrap;gap:8px;align-items:center}}
.card{{background:#fff;border:1px solid #d5dde5;border-left:5px solid #426ea5;border-radius:6px;padding:10px 12px;display:flex;flex-direction:column;gap:8px}}
.card.selected{{outline:2px solid #2455a4}}
.card.confirmed{{border-left-color:#1c7c4a}}
.card.unconfirmed{{border-left-color:#c97a16}}
.card-head{{display:flex;gap:8px;align-items:center;justify-content:space-between;flex-wrap:wrap}}
.field{{display:flex;flex-direction:column;gap:3px;font-size:12px}}
.field textarea,.field input[type=text],.field select{{width:100%;padding:5px 7px;border:1px solid #bcc7d1;border-radius:4px;font-size:13px}}
.field textarea{{min-height:48px;resize:vertical}}
.grid-picker{{display:grid;grid-template-columns:repeat(3,1fr);gap:4px;max-width:270px}}
.grid-picker button{{padding:4px 6px;font-size:11px;text-align:center}}
.grid-picker button.picked{{background:#2455a4;color:#fff;border-color:#2455a4;font-weight:600}}
.meta{{font-size:11px;color:#52616e;overflow-wrap:anywhere}}
.warn{{color:#a61b1b;font-size:12px;font-weight:600}}
.empty-msg{{background:#fff;border:1px dashed #bcc7d1;border-radius:6px;padding:14px;color:#52616e}}
.keys{{font-size:12px;color:#52616e;padding:0 18px 14px}}
kbd{{background:#e9eef3;border:1px solid #c5cfd9;border-radius:3px;padding:1px 5px;font:11px ui-monospace,monospace}}
@media(max-width:1020px){{.workspace{{grid-template-columns:1fr}}}}
</style>
<header>
  <div>
    <h1>Stage 3 Dev Label Review — {run_id}</h1>
    <div class="sub">Drafts from mutation manifest only (D-062) · Anton confirms every screenshot · {total} screenshots</div>
  </div>
  <div class="progress-wrap">
    <progress id="progress" value="0" max="{total}"></progress>
    <span id="progress-text">0 / {total} reviewed</span>
  </div>
</header>
<div class="bar">
  <button id="prev" title="Previous (← or k)">← Prev</button>
  <select id="screen-select" aria-label="Select screenshot"></select>
  <button id="next" title="Next (→ or j)">Next →</button>
  <div class="filters" id="filters">
    <button data-filter="all" class="active">All</button>
    <button data-filter="unreviewed">Unreviewed</button>
    <button data-filter="flagged">Flagged</button>
    <button data-filter="mutation">Mutated</button>
    <button data-filter="clean">Clean</button>
  </div>
  <span class="spacer"></span>
  <label style="cursor:pointer"><input type="file" id="import-file" accept=".json,application/json" hidden><button type="button" id="import-btn">Import JSON</button></label>
  <button id="export-btn" class="primary">Export JSON</button>
</div>
<p id="status" role="status"></p>
<main class="workspace">
  <section class="viewer-col">
    <div class="viewer-tools">
      <label>Zoom
        <select id="zoom">
          <option value="fit">Fit</option>
          <option value="1">100% (1:1)</option>
          <option value="2">2×</option>
        </select>
      </label>
      <label><input type="checkbox" id="show-boxes" checked> Label boxes</label>
      <label><input type="checkbox" id="show-grid"> 3×3 grid</label>
    </div>
    <div class="picture" id="picture">
      <div class="canvas" id="canvas">
        <img id="screenshot-img" alt="Screenshot under review">
        <svg id="overlay"></svg>
      </div>
    </div>
  </section>
  <section class="panel">
    <div class="screen-head" id="screen-head"></div>
    <div id="flags-container"></div>
    <div class="actions-row">
      <button id="add-label">+ Add label</button>
      <button id="undo-delete" disabled>Undo delete</button>
      <button id="confirm-all">Confirm all drafts</button>
      <button id="toggle-reviewed" class="ok">Mark reviewed</button>
    </div>
    <div id="labels"></div>
  </section>
</main>
<footer class="keys">
  Keys: <kbd>←</kbd>/<kbd>k</kbd> prev · <kbd>→</kbd>/<kbd>j</kbd> next · <kbd>c</kbd> confirm drafts ·
  <kbd>r</kbd> mark reviewed &amp; next unreviewed · <kbd>a</kbd> add label · <kbd>g</kbd> 3×3 grid ·
  <kbd>0</kbd>/<kbd>1</kbd>/<kbd>2</kbd> zoom Fit/100%/2×
</footer>
<script>globalThis.INITIAL_DRAFTS = {inline_data};</script>
<script>{script}</script>
</html>
"""
