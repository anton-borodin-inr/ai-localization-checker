/* Local candidate review; this script performs no network requests. */
(() => {
  const clone = value => JSON.parse(JSON.stringify(value));
  const sorted = value => Array.isArray(value) ? value.map(sorted) :
    value !== null && typeof value === "object" ? Object.fromEntries(
      Object.keys(value).sort().map(key => [key, sorted(value[key])])) : value;
  const canonical = value => JSON.stringify(sorted(value)) + "\n";
  const sha = async text => Array.from(new Uint8Array(await crypto.subtle.digest(
    "SHA-256", new TextEncoder().encode(text))), byte => byte.toString(16).padStart(2, "0")).join("");
  async function exportBundle(originalText, current, timing) {
    const initial = JSON.parse(originalText);
    const changed = canonical(initial) !== canonical(current);
    const candidate = clone(current);
    if (changed) candidate.parent_candidate_sha256 = await sha(originalText);
    const candidateText = changed ? canonical(candidate) : originalText;
    return {candidate_json: candidateText, approval: {
      status: "confirmed", accepted_by: "Anton", candidate_sha256: await sha(candidateText),
      initial_candidate_sha256: await sha(originalText), image_sha256: candidate.image.sha256,
      dump_sha256: candidate.dump.sha256, timing: clone(timing)
    }};
  }
  globalThis.ReferenceReview = {canonical, sha, exportBundle};
  if (typeof document === "undefined") return;
  const $ = id => document.getElementById(id);
  const originalText = new TextDecoder().decode(Uint8Array.from(atob(originalBase64), c => c.charCodeAt(0)));
  const candidate = JSON.parse(originalText);
  let selected = null, started = null, activeSince = null, activeMs = 0;
  const timingEvents = [];
  const regions = ["top-left", "top", "top-right", "left", "center", "right", "bottom-left", "bottom", "bottom-right"];
  const setMessage = text => { $("message").textContent = text; };
  const nowActive = () => activeMs + (activeSince === null ? 0 : performance.now() - activeSince);
  function updateTimer() {
    $("timer").textContent = started === null ? "Not started" :
      `${Math.floor(nowActive()/1000)}s active / ${Math.floor((performance.now()-started)/1000)}s elapsed`;
    $("confirm").disabled = started === null || !$("ack").checked;
  }
  function drawBoxes() {
    $("overlay").replaceChildren();
    candidate.rows.forEach(row => {
      for (const [toggle, key, color] of [["glyphs", "bounds", "#59d6ff"],
        ["owners", "owner_bounds", "#c595ff"], ["clips", "clip_bounds", "#ffaf42"]]) {
        if (!$(toggle).checked || row[key] === null) continue;
        const [left, top, right, bottom] = row[key];
        const rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
        Object.entries({x:left, y:top, width:right-left, height:bottom-top, fill:"none", stroke:color,
          "stroke-width": row.id === selected ? 4 : 1.5, "vector-effect":"non-scaling-stroke"})
          .forEach(([key,value]) => rect.setAttribute(key,value));
        $("overlay").append(rect);
      }
    });
  }
  function renderRows() {
    $("rows").replaceChildren();
    $("counts").textContent = `${candidate.rows.length} units · ${candidate.rows.filter(r => r.primary_denominator).length} primary · all pending confirmation`;
    candidate.rows.forEach((row, rowIndex) => {
      const card = document.createElement("article");
      card.className = `row${row.primary_denominator ? "" : " diagnostic"}${row.id === selected ? " selected" : ""}`;
      card.addEventListener("click", () => { selected = row.id; drawBoxes(); });
      const label = document.createElement("strong"); label.textContent = `Unit ${rowIndex + 1}`; label.title = row.id; card.append(label);
      const text = document.createElement("textarea"); text.value = row.text_seen;
      text.setAttribute("aria-label", "Visible text for " + row.id);
      text.addEventListener("input", () => { row.text_seen = text.value; row.human_edited = true; });
      card.append(text);
      const primaryLabel = document.createElement("label"), primary = document.createElement("input");
      primary.type = "checkbox"; primary.checked = row.primary_denominator;
      primary.addEventListener("change", () => {row.primary_denominator = primary.checked; row.human_edited = true; renderRows();});
      primaryLabel.append(primary, "Primary unit"); card.append(primaryLabel);
      const region = document.createElement("select"); region.setAttribute("aria-label", "Region for " + row.id);
      regions.forEach(value => { const option = document.createElement("option"); option.value=value;
        option.textContent=value; region.append(option); }); region.value=row.region;
      region.addEventListener("change", () => {row.region=region.value; row.human_edited=true;}); card.append(region);
      const remove = document.createElement("button"); remove.textContent="Remove";
      remove.addEventListener("click", () => { candidate.rows = candidate.rows.filter(r => r.id !== row.id); renderRows(); });
      card.append(remove);
      const metadata = document.createElement("p"); metadata.className="meta";
      metadata.textContent = `${row.visibility} · ${row.source} · ellipsis: ${row.ellipsis_applied} · overflow: ${row.overflow_x}/${row.overflow_y}`;
      card.append(metadata);
      if (row.warnings.length) { const warning=document.createElement("p"); warning.className="warning";
        warning.textContent=row.warnings.join("; "); card.append(warning); }
      const details=document.createElement("details"), summary=document.createElement("summary"), pre=document.createElement("pre");
      summary.textContent="Source and hidden input — never copied into visible text";
      pre.textContent=JSON.stringify({id:row.id,source_keys:row.source_keys,input_text:row.input_text,element_ids:row.element_ids},null,2);
      details.append(summary,pre); card.append(details); $("rows").append(card);
    }); drawBoxes();
  }
  $("start").addEventListener("click", () => {
    if (started !== null) return;
    started=performance.now(); activeSince=started;
    timingEvents.push({event:"start", at:new Date().toISOString(), elapsed_seconds:0});
    $("start").disabled=true; $("pause").disabled=false; updateTimer();
  });
  $("pause").addEventListener("click", () => {
    const paused=activeSince !== null;
    if (paused) {activeMs=nowActive();activeSince=null;} else activeSince=performance.now();
    timingEvents.push({event:paused?"pause":"resume",at:new Date().toISOString(),elapsed_seconds:(performance.now()-started)/1000});
    $("pause").textContent=paused?"Resume":"Pause"; updateTimer();
  });
  $("add").addEventListener("click", () => {
    let index=1; while(candidate.rows.some(r=>r.id===`human-${index}`)) index++;
    candidate.rows.push({id:`human-${index}`,section:"human",region:"center",text_seen:"",
      visibility:"human_entered",primary_denominator:false,bounds:null,owner_bounds:null,
      clip_bounds:null,visible_bounds:null,source:"human",human_edited:true,element_ids:[],source_keys:[],
      input_text:null,ellipsis_applied:false,overflow_x:false,overflow_y:false,warnings:[]}); renderRows();
    $("rows").lastElementChild.querySelector("textarea").focus();
  });
  ["glyphs","owners","clips"].forEach(id => $(id).addEventListener("change",drawBoxes));
  $("zoom").addEventListener("change",()=>{$("canvas").style.width=`${Number($("zoom").value)*100}%`;});
  $("ack").addEventListener("change",updateTimer);
  $("confirm").addEventListener("click", async () => {
    if (started === null || !$("ack").checked) return;
    if (candidate.rows.some(row => !row.text_seen.trim())) {setMessage("Edit or remove unresolved empty fragments first.");return;}
    $("confirm").disabled=true;
    try {
      const finished=new Date().toISOString(), finishedMono=performance.now();
      const elapsed=(finishedMono-started)/1000;
      const active=(activeMs+(activeSince===null?0:finishedMono-activeSince))/1000;
      const timing={started_at:timingEvents[0].at,finished_at:finished,
        elapsed_seconds:elapsed,active_seconds:active,
        events:[...timingEvents,{event:"finish",at:finished,elapsed_seconds:elapsed}]};
      const bundle=await exportBundle(originalText,candidate,timing);
      const url=URL.createObjectURL(new Blob([canonical(bundle)],{type:"application/json"}));
      const link=document.createElement("a");link.href=url;link.download="confirmation.json";link.click();
      setTimeout(()=>URL.revokeObjectURL(url),1000);
      setMessage("Exported hash-bound confirmation. Import it with l10n-reference confirm; later edits require a new confirmation.");
    } catch(error) {setMessage(`Export failed; nothing confirmed: ${error.message}`);}
    updateTimer();
  });
  renderRows(); updateTimer(); setInterval(updateTimer,1000);
})();
