/* Local Stage 3 label review UI (D-062). Performs no network requests. */
(() => {
  const DEFECT_TYPES = ["overflow", "wrong_language", "truncated_text", "other"];
  const REGIONS = [
    "top-left", "top", "top-right",
    "left", "center", "right",
    "bottom-left", "bottom", "bottom-right",
  ];
  const CLASS_COLORS = {
    overflow: "#ff5c5c",
    wrong_language: "#33b5ff",
    truncated_text: "#ffae33",
    other: "#c58bff",
  };
  const SVG_NS = "http://www.w3.org/2000/svg";
  const $ = id => document.getElementById(id);

  function clone(v) {
    return JSON.parse(JSON.stringify(v));
  }

  function initState(drafts) {
    return {
      run_id: drafts.run_id || "",
      commit: drafts.commit || "",
      builder_commit: drafts.builder_commit || "",
      screenshots: drafts.screenshots.map(s => ({
        png: s.png,
        screen: s.screen,
        language: s.language,
        role: s.role,
        batch: s.batch || "",
        image_size: s.image_size || [2400, 1080],
        review_flags: clone(s.review_flags || []),
        reviewed: false,
        labels: (s.labels || []).map((l, idx) => ({
          id: l.id || `draft-${idx + 1}`,
          source: l.source || "manifest",
          recipe_id: l.recipe_id || null,
          actor_path: l.actor_path || null,
          defect_type: l.defect_type,
          text_expected: l.text_expected || "",
          text_seen: l.text_seen || "",
          region: l.region || "center",
          note: l.note || "",
          glyph_bounds: l.glyph_bounds || null,
          owner_bounds: l.owner_bounds || null,
          confirmed: Boolean(l.confirmed),
        })),
      })),
    };
  }

  function validateScreenshot(shot) {
    for (let i = 0; i < shot.labels.length; i++) {
      const l = shot.labels[i];
      if (!l.confirmed) return `Label #${i + 1} is not confirmed yet.`;
      if (!DEFECT_TYPES.includes(l.defect_type)) return `Label #${i + 1} has invalid class.`;
      if (!REGIONS.includes(l.region)) return `Label #${i + 1} has invalid region.`;
      if (!l.text_seen.trim()) return `Label #${i + 1} has empty text_seen.`;
      if (!l.text_expected.trim()) return `Label #${i + 1} has empty text_expected.`;
      if (l.defect_type === "other" && !l.note.trim()) {
        return `Label #${i + 1} ('other') requires a non-empty note.`;
      }
    }
    return null;
  }

  function buildExport(state) {
    const reviewedCount = state.screenshots.filter(s => s.reviewed).length;
    return {
      export_version: 1,
      run_id: state.run_id,
      commit: state.commit,
      builder_commit: state.builder_commit,
      exported_at: new Date().toISOString(),
      reviewed: reviewedCount,
      total: state.screenshots.length,
      screenshots: state.screenshots.map(s => ({
        png: s.png,
        screen: s.screen,
        language: s.language,
        role: s.role,
        reviewed: Boolean(s.reviewed),
        labels: s.labels.map(l => ({
          id: l.id,
          defect_type: l.defect_type,
          text_expected: l.text_expected,
          text_seen: l.text_seen,
          region: l.region,
          note: l.note,
          confirmed: Boolean(l.confirmed),
          source: l.source || "human",
        })),
      })),
    };
  }

  globalThis.LabelReview = { initState, validateScreenshot, buildExport };
  if (typeof document === "undefined") return;

  const STORAGE_KEY = `l10n-label-review:${INITIAL_DRAFTS.run_id || "default"}`;
  let state = initState(INITIAL_DRAFTS);
  let activeFilter = "all";
  let currentIndex = 0;
  let selectedLabelId = null;
  let humanCounter = 1;
  const deletedStack = new Map();

  function setStatus(msg, isError = false) {
    const el = $("status");
    el.textContent = msg;
    el.style.color = isError ? "#a61b1b" : "#1c5a37";
  }

  function saveLocal() {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(buildExport(state)));
    } catch (_) {
      /* Ignore storage errors on restricted file:// origins. */
    }
  }

  function applyImportedExport(data) {
    if (!data || !Array.isArray(data.screenshots)) {
      throw new Error("Invalid export JSON: missing screenshots array.");
    }
    const byPng = new Map(data.screenshots.map(s => [s.png, s]));
    const initialByPng = new Map(INITIAL_DRAFTS.screenshots.map(s => [s.png, s]));
    let restored = 0;
    for (const shot of state.screenshots) {
      const saved = byPng.get(shot.png);
      if (!saved) continue;
      shot.reviewed = Boolean(saved.reviewed);
      const initialLabels = (initialByPng.get(shot.png) || {}).labels || [];
      const boxesById = new Map(
        initialLabels.map((l, idx) => [
          l.id || `draft-${idx + 1}`,
          {
            glyph_bounds: l.glyph_bounds || null,
            owner_bounds: l.owner_bounds || null,
            recipe_id: l.recipe_id || null,
            actor_path: l.actor_path || null,
          },
        ])
      );
      shot.labels = (saved.labels || []).map((l, idx) => {
        const lid = l.id || `restored-${idx + 1}`;
        const box = l.source === "manifest" ? boxesById.get(lid) || {} : {};
        return {
          id: lid,
          source: l.source || "human",
          recipe_id: box.recipe_id || null,
          actor_path: box.actor_path || null,
          defect_type: l.defect_type || "truncated_text",
          text_expected: l.text_expected || "",
          text_seen: l.text_seen || "",
          region: l.region || "center",
          note: l.note || "",
          glyph_bounds: box.glyph_bounds || null,
          owner_bounds: box.owner_bounds || null,
          confirmed: Boolean(l.confirmed),
        };
      });
      restored++;
    }
    return restored;
  }

  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      applyImportedExport(JSON.parse(raw));
      setStatus("Restored saved progress from this browser.");
    }
  } catch (_) {
    /* Start fresh if saved data is unreadable. */
  }

  function filteredIndices() {
    const out = [];
    state.screenshots.forEach((s, i) => {
      if (activeFilter === "unreviewed" && s.reviewed) return;
      if (activeFilter === "flagged" && !s.review_flags.length) return;
      if (activeFilter === "mutation" && s.role !== "mutation") return;
      if (activeFilter === "clean" && s.role !== "clean") return;
      out.push(i);
    });
    return out;
  }

  function currentShot() {
    return state.screenshots[currentIndex];
  }

  function updateProgress() {
    const reviewed = state.screenshots.filter(s => s.reviewed).length;
    const total = state.screenshots.length;
    $("progress").value = reviewed;
    $("progress").max = total;
    $("progress-text").textContent = `${reviewed} / ${total} reviewed`;
  }

  function renderSelector() {
    const select = $("screen-select");
    const indices = filteredIndices();
    select.replaceChildren();
    if (!indices.length) {
      const opt = document.createElement("option");
      opt.textContent = "(no screenshots match filter)";
      select.append(opt);
      $("prev").disabled = true;
      $("next").disabled = true;
      return;
    }
    if (!indices.includes(currentIndex)) {
      currentIndex = indices[0];
    }
    for (const idx of indices) {
      const s = state.screenshots[idx];
      const opt = document.createElement("option");
      opt.value = String(idx);
      const mark = s.reviewed ? "✓" : "○";
      const flag = s.review_flags.length ? " ⚑" : "";
      opt.textContent = `${mark} [${idx + 1}/${state.screenshots.length}] ${s.screen} (${s.language}, ${s.role}, ${s.labels.length})${flag}`;
      if (idx === currentIndex) opt.selected = true;
      select.append(opt);
    }
    const pos = indices.indexOf(currentIndex);
    $("prev").disabled = pos <= 0;
    $("next").disabled = pos >= indices.length - 1;
  }

  function applyZoom() {
    const shot = currentShot();
    const [w] = shot.image_size;
    const mode = $("zoom").value;
    if (mode === "fit") {
      $("canvas").style.width = "100%";
    } else {
      $("canvas").style.width = `${w * Number(mode)}px`;
    }
  }

  function drawOverlay() {
    const shot = currentShot();
    const [w, h] = shot.image_size;
    const svg = $("overlay");
    svg.setAttribute("viewBox", `0 0 ${w} ${h}`);
    svg.replaceChildren();

    if ($("show-grid").checked) {
      for (const x of [w / 3, (2 * w) / 3]) {
        const line = document.createElementNS(SVG_NS, "line");
        line.setAttribute("x1", x);
        line.setAttribute("y1", 0);
        line.setAttribute("x2", x);
        line.setAttribute("y2", h);
        line.setAttribute("stroke", "rgba(255,255,255,0.55)");
        line.setAttribute("stroke-width", "2");
        line.setAttribute("stroke-dasharray", "10 8");
        svg.append(line);
      }
      for (const y of [h / 3, (2 * h) / 3]) {
        const line = document.createElementNS(SVG_NS, "line");
        line.setAttribute("x1", 0);
        line.setAttribute("y1", y);
        line.setAttribute("x2", w);
        line.setAttribute("y2", y);
        line.setAttribute("stroke", "rgba(255,255,255,0.55)");
        line.setAttribute("stroke-width", "2");
        line.setAttribute("stroke-dasharray", "10 8");
        svg.append(line);
      }
      REGIONS.forEach((name, idx) => {
        const col = idx % 3;
        const row = Math.floor(idx / 3);
        const text = document.createElementNS(SVG_NS, "text");
        text.setAttribute("x", col * (w / 3) + 18);
        text.setAttribute("y", row * (h / 3) + 34);
        text.setAttribute("fill", "rgba(255,255,255,0.85)");
        text.setAttribute("font-size", "24");
        text.setAttribute("font-family", "system-ui,sans-serif");
        text.setAttribute("paint-order", "stroke");
        text.setAttribute("stroke", "rgba(0,0,0,0.75)");
        text.setAttribute("stroke-width", "4");
        text.textContent = name;
        svg.append(text);
      });
    }

    if (!$("show-boxes").checked) return;

    shot.labels.forEach((label, idx) => {
      const color = CLASS_COLORS[label.defect_type] || "#ffffff";
      const isSelected = label.id === selectedLabelId;
      if (
        label.owner_bounds &&
        (!label.glyph_bounds || JSON.stringify(label.owner_bounds) !== JSON.stringify(label.glyph_bounds))
      ) {
        const [x0, y0, x1, y1] = label.owner_bounds;
        const ownerRect = document.createElementNS(SVG_NS, "rect");
        ownerRect.setAttribute("x", x0);
        ownerRect.setAttribute("y", y0);
        ownerRect.setAttribute("width", Math.max(1, x1 - x0));
        ownerRect.setAttribute("height", Math.max(1, y1 - y0));
        ownerRect.setAttribute("fill", "none");
        ownerRect.setAttribute("stroke", "#ffffff");
        ownerRect.setAttribute("stroke-width", "2");
        ownerRect.setAttribute("stroke-dasharray", "6 4");
        ownerRect.setAttribute("vector-effect", "non-scaling-stroke");
        svg.append(ownerRect);
      }
      const box = label.glyph_bounds || label.owner_bounds;
      if (!box) return;
      const [x0, y0, x1, y1] = box;
      const rect = document.createElementNS(SVG_NS, "rect");
      rect.setAttribute("class", "box");
      rect.setAttribute("x", x0);
      rect.setAttribute("y", y0);
      rect.setAttribute("width", Math.max(1, x1 - x0));
      rect.setAttribute("height", Math.max(1, y1 - y0));
      rect.setAttribute("fill", isSelected ? "rgba(255,255,255,0.14)" : "none");
      rect.setAttribute("stroke", color);
      rect.setAttribute("stroke-width", isSelected ? "4" : "2.5");
      rect.setAttribute("vector-effect", "non-scaling-stroke");
      rect.addEventListener("click", () => {
        selectedLabelId = label.id;
        renderLabels();
        drawOverlay();
      });
      svg.append(rect);

      const tag = document.createElementNS(SVG_NS, "text");
      tag.setAttribute("x", x0);
      tag.setAttribute("y", Math.max(24, y0 - 8));
      tag.setAttribute("fill", color);
      tag.setAttribute("font-size", "22");
      tag.setAttribute("font-weight", "700");
      tag.setAttribute("paint-order", "stroke");
      tag.setAttribute("stroke", "#000000");
      tag.setAttribute("stroke-width", "4");
      tag.textContent = `#${idx + 1} ${label.defect_type}`;
      svg.append(tag);
    });
  }

  function renderFlags(shot) {
    const container = $("flags-container");
    container.replaceChildren();
    if (!shot.review_flags.length) return;
    const box = document.createElement("div");
    box.className = "flags";
    const title = document.createElement("strong");
    title.textContent = `Review flag hint (${shot.review_flags.length} unmutated text difference${shot.review_flags.length > 1 ? "s" : ""}):`;
    box.append(title);
    for (const flag of shot.review_flags) {
      const pre = document.createElement("pre");
      pre.textContent = JSON.stringify(flag, null, 2);
      box.append(pre);
    }
    container.append(box);
  }

  function renderHeader(shot) {
    const head = $("screen-head");
    head.replaceChildren();
    const h2 = document.createElement("h2");
    h2.textContent = shot.png;
    head.append(h2);

    const badges = document.createElement("div");
    const rev = document.createElement("span");
    rev.className = `badge ${shot.reviewed ? "reviewed" : "pending"}`;
    rev.textContent = shot.reviewed ? "Reviewed" : "Pending review";
    const role = document.createElement("span");
    role.className = `badge ${shot.role}`;
    role.textContent = shot.role === "clean" ? "Clean control" : "Mutated";
    const info = document.createElement("span");
    info.className = "meta";
    info.textContent = `${shot.screen} · ${shot.language.toUpperCase()} · ${shot.labels.length} label(s)`;
    badges.append(rev, role, info);
    head.append(badges);

    $("toggle-reviewed").textContent = shot.reviewed ? "Unmark reviewed" : "Mark reviewed";
    const undoList = deletedStack.get(shot.png) || [];
    $("undo-delete").disabled = undoList.length === 0;
  }

  function makeGridPicker(label, onChange) {
    const grid = document.createElement("div");
    grid.className = "grid-picker";
    for (const region of REGIONS) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.textContent = region;
      if (label.region === region) btn.className = "picked";
      btn.addEventListener("click", () => {
        label.region = region;
        onChange();
      });
      grid.append(btn);
    }
    return grid;
  }

  function renderLabels() {
    const shot = currentShot();
    const container = $("labels");
    container.replaceChildren();

    if (!shot.labels.length) {
      const empty = document.createElement("div");
      empty.className = "empty-msg";
      empty.textContent =
        shot.role === "clean"
          ? "Clean control (0 draft labels). Inspect the screenshot and mark reviewed, or add a label if you spot a defect."
          : "No labels on this screenshot. Add a label if a defect is visible, or mark reviewed if clean.";
      container.append(empty);
      return;
    }

    shot.labels.forEach((label, idx) => {
      const card = document.createElement("article");
      card.className = `card ${label.confirmed ? "confirmed" : "unconfirmed"}${label.id === selectedLabelId ? " selected" : ""}`;
      card.addEventListener("click", () => {
        if (selectedLabelId !== label.id) {
          selectedLabelId = label.id;
          drawOverlay();
          container.querySelectorAll(".card").forEach((el, i) => {
            el.classList.toggle("selected", shot.labels[i]?.id === selectedLabelId);
          });
        }
      });

      const head = document.createElement("div");
      head.className = "card-head";
      const title = document.createElement("strong");
      title.textContent = `Label #${idx + 1} (${label.source === "manifest" ? "draft" : "added"})`;
      const btnGroup = document.createElement("div");
      btnGroup.style.display = "flex";
      btnGroup.style.gap = "6px";

      const confirmBtn = document.createElement("button");
      confirmBtn.type = "button";
      confirmBtn.className = label.confirmed ? "ok" : "";
      confirmBtn.textContent = label.confirmed ? "✓ Confirmed" : "Confirm";
      confirmBtn.addEventListener("click", e => {
        e.stopPropagation();
        label.confirmed = !label.confirmed;
        if (!label.confirmed) shot.reviewed = false;
        saveLocal();
        renderAll();
      });

      const delBtn = document.createElement("button");
      delBtn.type = "button";
      delBtn.className = "danger";
      delBtn.textContent = "Delete";
      delBtn.addEventListener("click", e => {
        e.stopPropagation();
        const stack = deletedStack.get(shot.png) || [];
        stack.push({ index: idx, label: clone(label) });
        deletedStack.set(shot.png, stack);
        shot.labels.splice(idx, 1);
        saveLocal();
        renderAll();
      });

      btnGroup.append(confirmBtn, delBtn);
      head.append(title, btnGroup);
      card.append(head);

      const typeField = document.createElement("label");
      typeField.className = "field";
      typeField.textContent = "Class (defect_type)";
      const typeSelect = document.createElement("select");
      for (const dt of DEFECT_TYPES) {
        const opt = document.createElement("option");
        opt.value = dt;
        opt.textContent = dt;
        if (label.defect_type === dt) opt.selected = true;
        typeSelect.append(opt);
      }
      typeSelect.addEventListener("change", () => {
        label.defect_type = typeSelect.value;
        saveLocal();
        renderAll();
      });
      typeField.append(typeSelect);
      card.append(typeField);

      const seenField = document.createElement("label");
      seenField.className = "field";
      seenField.textContent = "text_seen (visible on screenshot)";
      const seenInput = document.createElement("textarea");
      seenInput.value = label.text_seen;
      seenInput.addEventListener("input", () => {
        label.text_seen = seenInput.value;
        saveLocal();
      });
      seenField.append(seenInput);
      card.append(seenField);

      const expField = document.createElement("label");
      expField.className = "field";
      expField.textContent = "text_expected";
      const expInput = document.createElement("textarea");
      expInput.value = label.text_expected;
      expInput.addEventListener("input", () => {
        label.text_expected = expInput.value;
        saveLocal();
      });
      expField.append(expInput);
      card.append(expField);

      const regField = document.createElement("div");
      regField.className = "field";
      const regLabel = document.createElement("span");
      regLabel.textContent = `Region (3×3 centre cell): ${label.region}`;
      regField.append(
        regLabel,
        makeGridPicker(label, () => {
          saveLocal();
          renderLabels();
        })
      );
      card.append(regField);

      const noteField = document.createElement("label");
      noteField.className = "field";
      noteField.textContent = label.defect_type === "other" ? "Note (required for 'other')" : "Note (optional)";
      const noteInput = document.createElement("input");
      noteInput.type = "text";
      noteInput.value = label.note;
      noteInput.addEventListener("input", () => {
        label.note = noteInput.value;
        saveLocal();
      });
      noteField.append(noteInput);
      card.append(noteField);

      if (label.defect_type === "other" && !label.note.trim()) {
        const warn = document.createElement("div");
        warn.className = "warn";
        warn.textContent = "A note is required when class is 'other'.";
        card.append(warn);
      }

      if (label.recipe_id || label.actor_path) {
        const meta = document.createElement("div");
        meta.className = "meta";
        meta.textContent = [label.recipe_id, label.actor_path].filter(Boolean).join(" · ");
        card.append(meta);
      }

      container.append(card);
    });
  }

  function renderAll() {
    updateProgress();
    renderSelector();
    const shot = currentShot();
    if (!shot) return;
    const img = $("screenshot-img");
    if (img.getAttribute("src") !== shot.png) {
      img.setAttribute("src", shot.png);
    }
    applyZoom();
    renderHeader(shot);
    renderFlags(shot);
    renderLabels();
    drawOverlay();
  }

  function step(delta) {
    const indices = filteredIndices();
    const pos = indices.indexOf(currentIndex);
    if (pos === -1) return;
    const nextPos = pos + delta;
    if (nextPos >= 0 && nextPos < indices.length) {
      currentIndex = indices[nextPos];
      selectedLabelId = null;
      renderAll();
    }
  }

  function jumpToNextUnreviewed() {
    const total = state.screenshots.length;
    for (let offset = 1; offset <= total; offset++) {
      const idx = (currentIndex + offset) % total;
      if (!state.screenshots[idx].reviewed) {
        currentIndex = idx;
        selectedLabelId = null;
        return true;
      }
    }
    return false;
  }

  function addNewLabel() {
    const shot = currentShot();
    const newLabel = {
      id: `human-${humanCounter++}`,
      source: "human",
      recipe_id: null,
      actor_path: null,
      defect_type: "truncated_text",
      text_expected: "",
      text_seen: "",
      region: "center",
      note: "",
      glyph_bounds: null,
      owner_bounds: null,
      confirmed: true,
    };
    shot.labels.push(newLabel);
    shot.reviewed = false;
    selectedLabelId = newLabel.id;
    saveLocal();
    renderAll();
    const lastCard = $("labels").lastElementChild;
    const firstTextarea = lastCard && lastCard.querySelector("textarea");
    if (firstTextarea) firstTextarea.focus();
  }

  function confirmAllOnScreen() {
    const shot = currentShot();
    for (const label of shot.labels) {
      label.confirmed = true;
    }
    saveLocal();
    renderAll();
    setStatus(`Confirmed ${shot.labels.length} label(s) on ${shot.png}.`);
  }

  function toggleReviewed(advance = false) {
    const shot = currentShot();
    if (shot.reviewed && !advance) {
      shot.reviewed = false;
      saveLocal();
      renderAll();
      setStatus(`Unmarked ${shot.png}.`);
      return;
    }
    const err = validateScreenshot(shot);
    if (err) {
      setStatus(`Cannot mark reviewed: ${err}`, true);
      return;
    }
    shot.reviewed = true;
    saveLocal();
    if (advance) {
      const moved = jumpToNextUnreviewed();
      renderAll();
      setStatus(moved ? `Marked reviewed and moved to next unreviewed.` : `All ${state.screenshots.length} screenshots reviewed!`);
    } else {
      renderAll();
      setStatus(`Marked ${shot.png} reviewed.`);
    }
  }

  $("prev").addEventListener("click", () => step(-1));
  $("next").addEventListener("click", () => step(1));
  $("screen-select").addEventListener("change", () => {
    currentIndex = Number($("screen-select").value);
    selectedLabelId = null;
    renderAll();
  });

  $("filters").addEventListener("click", e => {
    const btn = e.target.closest("button[data-filter]");
    if (!btn) return;
    activeFilter = btn.dataset.filter;
    $("filters").querySelectorAll("button").forEach(b => b.classList.toggle("active", b === btn));
    selectedLabelId = null;
    renderAll();
  });

  $("zoom").addEventListener("change", applyZoom);
  $("show-boxes").addEventListener("change", drawOverlay);
  $("show-grid").addEventListener("change", drawOverlay);
  $("add-label").addEventListener("click", addNewLabel);
  $("confirm-all").addEventListener("click", confirmAllOnScreen);
  $("toggle-reviewed").addEventListener("click", () => toggleReviewed(false));
  $("undo-delete").addEventListener("click", () => {
    const shot = currentShot();
    const stack = deletedStack.get(shot.png) || [];
    const last = stack.pop();
    if (!last) return;
    shot.labels.splice(Math.min(last.index, shot.labels.length), 0, last.label);
    shot.reviewed = false;
    saveLocal();
    renderAll();
    setStatus("Restored deleted label.");
  });

  $("export-btn").addEventListener("click", () => {
    const payload = buildExport(state);
    const json = JSON.stringify(payload, null, 2) + "\n";
    const url = URL.createObjectURL(new Blob([json], { type: "application/json" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = "label-review-export.json";
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    if (payload.reviewed < payload.total) {
      setStatus(
        `Exported partial progress (${payload.reviewed}/${payload.total} reviewed). l10n-label write requires all ${payload.total} reviewed.`,
        true
      );
    } else {
      setStatus(`Exported all ${payload.total}/${payload.total} reviewed screenshots to label-review-export.json.`);
    }
  });

  $("import-btn").addEventListener("click", () => $("import-file").click());
  $("import-file").addEventListener("change", async e => {
    const file = e.target.files && e.target.files[0];
    if (!file) return;
    try {
      const parsed = JSON.parse(await file.text());
      const count = applyImportedExport(parsed);
      saveLocal();
      renderAll();
      setStatus(`Imported decisions for ${count} screenshot(s) from ${file.name}.`);
    } catch (err) {
      setStatus(`Import failed: ${err.message}`, true);
    }
    e.target.value = "";
  });

  document.addEventListener("keydown", e => {
    const tag = document.activeElement && document.activeElement.tagName;
    if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
    if (e.metaKey || e.ctrlKey || e.altKey) return;
    if (e.key === "ArrowLeft" || e.key === "k") {
      e.preventDefault();
      step(-1);
    } else if (e.key === "ArrowRight" || e.key === "j") {
      e.preventDefault();
      step(1);
    } else if (e.key === "c") {
      e.preventDefault();
      confirmAllOnScreen();
    } else if (e.key === "r") {
      e.preventDefault();
      toggleReviewed(true);
    } else if (e.key === "a") {
      e.preventDefault();
      addNewLabel();
    } else if (e.key === "g") {
      e.preventDefault();
      $("show-grid").checked = !$("show-grid").checked;
      drawOverlay();
    } else if (e.key === "0") {
      $("zoom").value = "fit";
      applyZoom();
    } else if (e.key === "1") {
      $("zoom").value = "1";
      applyZoom();
    } else if (e.key === "2") {
      $("zoom").value = "2";
      applyZoom();
    }
  });

  renderAll();
})();
