// Job Hunter UI helpers: JSON posts, the run dock (live log on any page), health, copy.
(function () {
  const $ = (sel, root) => (root || document).querySelector(sel);
  const $$ = (sel, root) => Array.from((root || document).querySelectorAll(sel));

  // Reloading after an action must not lose the reader's place: remember the scroll position and
  // which control of which job row had focus, and put focus back after the page comes up.
  const PLACE_KEY = 'jh_place';
  function reloadHere() {
    try {
      const el = document.activeElement;
      const card = el && el.closest ? el.closest('.job-card') : null;
      const place = { path: location.pathname + location.search, y: window.scrollY };
      if (card) {
        place.card = $$('.job-card').indexOf(card);
        place.ctl = $$('button, a', card).indexOf(el);
      }
      sessionStorage.setItem(PLACE_KEY, JSON.stringify(place));
    } catch (e) { /* storage unavailable: reload anyway */ }
    location.reload();
  }

  (function restorePlace() {
    let place = null;
    try {
      place = JSON.parse(sessionStorage.getItem(PLACE_KEY) || 'null');
      sessionStorage.removeItem(PLACE_KEY);
    } catch (e) { return; }
    if (!place || place.path !== location.pathname + location.search) return;
    window.scrollTo(0, place.y || 0);
    const cards = $$('.job-card');
    const card = place.card >= 0 && cards.length ? cards[Math.min(place.card, cards.length - 1)] : null;
    const target = card ? ($$('button, a', card)[Math.max(place.ctl, 0)] || card.querySelector('a, button')) : $('#main');
    if (target) target.focus({ preventScroll: true });
  })();

  const UNDO_KEY = 'jh_undo';

  function toast(message) {
    const el = $('#toast');
    el.textContent = message;
    el.hidden = false;
    clearTimeout(toast.t);
    toast.t = setTimeout(() => (el.hidden = true), 4500);
  }

  function svgIcon(name) {
    const ns = 'http://www.w3.org/2000/svg';
    const svg = document.createElementNS(ns, 'svg');
    svg.setAttribute('class', 'ic');
    svg.setAttribute('aria-hidden', 'true');
    svg.setAttribute('focusable', 'false');
    const use = document.createElementNS(ns, 'use');
    use.setAttribute('href', '#i-' + name);
    svg.append(use);
    return svg;
  }

  async function post(url, body) {
    const res = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body || {}) });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) { const err = new Error(data.error || 'Request failed (' + res.status + ')'); err.data = data; throw err; }
    return data;
  }

  async function act(fn, reload) {
    try { await fn(); if (reload !== false) reloadHere(); return true; }
    catch (err) { toast(err.message); return false; }
  }

  // A stage change reloads the page; the toast that follows offers to put it back.
  (function undoToast() {
    let u = null;
    try {
      u = JSON.parse(sessionStorage.getItem(UNDO_KEY) || 'null');
      sessionStorage.removeItem(UNDO_KEY);
    } catch (e) { return; }
    if (!u) return;
    const el = $('#toast');
    el.textContent = u.text + ' ';
    const undo = document.createElement('button');
    undo.type = 'button';
    undo.className = 'toast-undo';
    undo.textContent = 'Undo';
    undo.addEventListener('click', () => act(() => post('/api/jobs/' + u.job + '/stage', { stage: u.prev })));
    el.append(undo);
    el.hidden = false;
    clearTimeout(toast.t);
    toast.t = setTimeout(() => (el.hidden = true), 8000);
  })();

  // ---------- run dock ----------
  const dock = $('#dock');
  const KEY = 'jh_run';
  let timer = null;

  function setDock(state, text) {
    $('#dock-status').textContent = text;
    $('#dock-status').className = 'badge ' + (state === 'ok' ? 'good' : state === 'bad' ? 'bad' : 'warn');
    $('#dock-dot').className = 'dock-dot ' + (state === 'ok' ? 'ok' : state === 'bad' ? 'bad' : '');
  }

  function poll(run, since) {
    fetch('/api/runs/' + run.id + '?since=' + since).then((r) => r.json()).then((s) => {
      const log = $('#dock-log');
      if (s.log) { log.textContent += (log.textContent ? '\n' : '') + s.log; log.scrollTop = log.scrollHeight; }
      if (s.status === 'running') { timer = setTimeout(() => poll(run, s.next), 1000); return; }
      sessionStorage.removeItem(KEY);
      $$('[data-run],[data-runcard]').forEach((b) => (b.disabled = false));
      const ok = s.status === 'ok';
      setDock(ok ? 'ok' : 'bad', ok ? 'done' : 'failed');
      $('#dock-result').textContent = ok ? 'Finished.' : 'Exited with code ' + s.exit_code + '. Read the log above.';
      $('#dock-foot').hidden = false;
      if (ok && run.reload) { $('#dock-result').textContent = 'Finished. Updating this page…'; setTimeout(() => reloadHere(), 1200); }
    }).catch(() => setDock('bad', 'lost connection'));
  }

  function openDock(run, resumed) {
    dock.hidden = false;
    dock.classList.remove('min');
    $('#dock-title').textContent = run.label || 'Working…';
    $('#dock-foot').hidden = true;
    if (!resumed) $('#dock-log').textContent = '';
    setDock('run', 'running');
    $$('[data-run],[data-runcard]').forEach((b) => (b.disabled = true));
    clearTimeout(timer);
    poll(run, 0);
  }

  async function startRun(body, label, reload) {
    try {
      const run = await post('/api/runs', body);
      const info = { id: run.id, label: label, reload: !!reload };
      sessionStorage.setItem(KEY, JSON.stringify(info));
      openDock(info, false);
    } catch (err) { toast(err.message); }
  }

  if (dock) {
    $('#dock-toggle').addEventListener('click', () => dock.classList.toggle('min'));
    $('#dock-close').addEventListener('click', () => { dock.hidden = true; });
    $('#dock-refresh').addEventListener('click', () => reloadHere());
    try {
      const saved = JSON.parse(sessionStorage.getItem(KEY) || 'null');
      if (saved) openDock(saved, true);
    } catch (e) { /* ignore */ }
  }

  document.addEventListener('click', (ev) => {
    const runBtn = ev.target.closest('[data-run]');
    if (runBtn) {
      startRun(JSON.parse(runBtn.dataset.run), runBtn.dataset.label, runBtn.hasAttribute('data-reload'));
      return;
    }
    const card = ev.target.closest('[data-runcard]');
    if (card) {
      const box = card.closest('.runcard');
      const opt = (name) => $('[data-opt=' + name + ']', box);
      const body = { id: card.dataset.runcard };
      if (opt('dry_run')) body.dry_run = opt('dry_run').checked;
      if (opt('force')) body.force = opt('force').checked;
      if (opt('limit') && opt('limit').value) body.limit = parseInt(opt('limit').value, 10);
      if (opt('jobs') && opt('jobs').value.trim()) {
        body.jobs = opt('jobs').value.split(/[\s,]+/).filter(Boolean).map((v) => parseInt(v, 10));
        if (body.jobs.some(Number.isNaN)) return toast('Posting ids must be numbers');
      }
      startRun(body, card.dataset.label, false);
      return;
    }
    const el = ev.target.closest('[data-post]');
    if (el) {
      if (el.dataset.confirm && !confirm(el.dataset.confirm)) return;
      act(() => post(el.dataset.post, JSON.parse(el.dataset.json || '{}')));
      return;
    }
    const copy = ev.target.closest('[data-copy]');
    if (copy) { navigator.clipboard.writeText($(copy.dataset.copy).textContent).then(() => toast('Copied')); return; }
    const notes = ev.target.closest('[data-notes-job]');
    if (notes) {
      act(() => post('/api/jobs/' + notes.dataset.notesJob + '/notes', { notes: $('#notes').value }), false).then((ok) => ok && toast('Notes saved'));
      return;
    }
    const save = ev.target.closest('[data-save-interview]');
    if (save) {
      const box = save.closest('[data-interview]');
      const body = {};
      $$('[data-field]', box).forEach((f) => (body[f.dataset.field] = f.value));
      act(() => post('/api/interviews/' + box.dataset.interview, body), false).then((ok) => ok && toast('Interview saved'));
    }
  });

  document.addEventListener('change', (ev) => {
    const sel = ev.target.closest('[data-stage-job]');
    if (!sel) return;
    const prev = sel.dataset.prev;
    const label = sel.selectedOptions[0].textContent;
    act(async () => {
      await post('/api/jobs/' + sel.dataset.stageJob + '/stage', { stage: sel.value });
      try {
        if (prev) sessionStorage.setItem(UNDO_KEY, JSON.stringify({ job: sel.dataset.stageJob, prev, text: 'Moved to ' + label + '.' }));
      } catch (e) { /* no undo without storage */ }
    });
  });

  document.addEventListener('submit', (ev) => {
    const form = ev.target.closest('[data-new-interview]');
    if (!form) return;
    ev.preventDefault();
    act(() => post('/api/jobs/' + form.dataset.newInterview + '/interviews', Object.fromEntries(new FormData(form))));
  });

  // ---------- settings forms ----------
  function initTags(box) {
    let values = [];
    try { values = JSON.parse(box.dataset.value || '[]'); } catch (e) { values = []; }
    const input = document.createElement('input');
    input.type = 'text';
    input.placeholder = 'Type and press Enter';
    if (box.dataset.inputId) input.id = box.dataset.inputId;
    if (box.dataset.desc) input.setAttribute('aria-describedby', box.dataset.desc);
    input.setAttribute('aria-label', box.dataset.label || 'Add an item');
    function render() {
      $$('.tag', box).forEach((t) => t.remove());
      values.forEach((v, i) => {
        const tag = document.createElement('span');
        tag.className = 'tag';
        tag.append(document.createTextNode(v));
        const x = document.createElement('button');
        x.type = 'button';
        x.setAttribute('aria-label', 'Remove ' + v);
        x.append(svgIcon('x'));
        x.addEventListener('click', () => { values.splice(i, 1); render(); });
        tag.append(x);
        box.insertBefore(tag, input);
      });
    }
    function add(raw) {
      raw.split(',').map((t) => t.trim()).filter(Boolean).forEach((t) => { if (!values.includes(t)) values.push(t); });
      input.value = '';
      render();
    }
    input.addEventListener('keydown', (ev) => {
      if (ev.key === 'Enter' || ev.key === ',') { ev.preventDefault(); add(input.value); }
      else if (ev.key === 'Backspace' && !input.value && values.length) { values.pop(); render(); }
    });
    input.addEventListener('blur', () => { if (input.value.trim()) add(input.value); });
    box.append(input);
    box.peek = () => values.concat(input.value.trim() ? [input.value.trim()] : []);
    box.getValues = () => { if (input.value.trim()) add(input.value); return values.slice(); };
    render();
  }
  $$('.tags[data-cfg]').forEach(initTags);

  function readField(el, peek) {
    switch (el.dataset.type) {
      case 'tags': return peek ? el.peek() : el.getValues();
      case 'checks': return $$('input:checked', el).map((c) => c.value);
      case 'number': {
        const v = el.value.trim();
        if (v === '') return el.hasAttribute('data-nullable') ? null : undefined;
        const n = Number(v);
        return Number.isFinite(n) ? n : undefined;
      }
      default: return el.value;
    }
  }

  function setNested(obj, path, value) {
    const keys = path.split('.');
    keys.slice(0, -1).forEach((k) => { obj = obj[k] = obj[k] || {}; });
    obj[keys[keys.length - 1]] = value;
  }

  function showErrors(card, errors) {
    $$('.field', card).forEach((f) => { f.classList.remove('invalid'); const e = $('.error-text', f); if (e) e.hidden = true; });
    (errors || []).forEach((err) => {
      const el = $$('[data-cfg]', card).find((x) => x.dataset.cfg === err.field);
      const field = el && el.closest('.field');
      if (field) { field.classList.add('invalid'); const e = $('.error-text', field); e.textContent = err.message; e.hidden = false; }
    });
  }

  // ---------- Settings: one tab at a time, one dirty-aware save ----------
  let showPanel = () => {};
  let baseline = '';
  let refreshDirty = () => {};

  function collectConfig(peek) {
    const updates = {};
    $$('[data-card] [data-cfg]').forEach((el) => { const v = readField(el, peek); if (v !== undefined) setNested(updates, el.dataset.cfg, v); });
    return updates;
  }

  document.addEventListener('click', async (ev) => {
    const saveCfg = ev.target.closest('[data-save-cfg]');
    if (saveCfg) {
      const state = $('#savebar .save-state');
      if (saveCfg.disabled) return;
      $$('[data-save-cfg]').forEach((b) => (b.disabled = true));
      try {
        await post('/api/config', { updates: collectConfig(false) });
        $$('[data-card]').forEach((card) => showErrors(card, []));
        baseline = JSON.stringify(collectConfig(true));
        refreshDirty();
        state.textContent = 'Saved';
        state.className = 'save-state ok small';
        if (saveCfg.dataset.then === 'refilter') startRun({ id: 'refilter' }, 'Re-filtering with your new criteria', true);
      } catch (err) {
        let detail = err.message;
        if (err.data && err.data.errors) {
          $$('[data-card]').forEach((card) => showErrors(card, err.data.errors));
          detail = err.data.errors.map((e) => e.field + ': ' + e.message).join(' · ');
          const bad = $$('[data-cfg]').find((x) => x.dataset.cfg === err.data.errors[0].field);
          if (bad) showPanel(bad.closest('[data-card]').id);
        }
        refreshDirty();
        state.textContent = 'Not saved: ' + detail;
        state.className = 'save-state bad small';
      }
      return;
    }
    const saveFile = ev.target.closest('[data-save-file]');
    if (saveFile) {
      const name = saveFile.dataset.saveFile;
      const area = $('[data-file="' + name + '"]');
      const state = $('.save-state', saveFile.closest('.form-actions'));
      if (area.dataset.loaded !== '1') { state.textContent = 'The file has not loaded; nothing was saved.'; state.className = 'save-state bad small'; return; }
      try {
        await post('/api/files/' + name, { content: area.value });
        state.textContent = 'Saved ✓ (previous version kept as .bak)';
        state.className = 'save-state ok small';
      } catch (err) {
        state.textContent = 'Not saved: ' + err.message;
        state.className = 'save-state bad small';
      }
    }
  });

  $$('[data-file]').forEach((area) => {
    fetch('/api/files/' + area.dataset.file).then((r) => r.json()).then((f) => {
      if (f.error) { area.placeholder = f.error; area.disabled = true; return; }
      area.value = f.content || '';
      area.dataset.loaded = '1';
      if (!f.exists) area.placeholder = 'File not found: ' + f.path + ' (saving creates it)';
    }).catch(() => { area.placeholder = 'Could not load the file'; area.disabled = true; });
  });

  const settingsTabs = $('#settings-tabs');
  if (settingsTabs) {
    const tabs = $$('a', settingsTabs);
    const ids = tabs.map((t) => t.getAttribute('href').slice(1));
    const bar = $('#savebar');
    const saveBtn = $('[data-save-cfg]:not([data-then])');
    const refilterBtn = $('[data-save-cfg][data-then]');
    showPanel = (id, focus) => {
      if (!ids.includes(id)) id = ids[0];
      tabs.forEach((t) => {
        const on = t.getAttribute('href') === '#' + id;
        t.classList.toggle('on', on);
        if (on) t.setAttribute('aria-current', 'true'); else t.removeAttribute('aria-current');
      });
      ids.forEach((x) => { document.getElementById(x).hidden = x !== id; });
      bar.hidden = !document.getElementById(id).hasAttribute('data-card');
      try { history.replaceState(null, '', '#' + id); } catch (e) { /* ignore */ }
      if (focus) document.getElementById(id).focus({ preventScroll: true });
    };
    tabs.forEach((t) => t.addEventListener('click', (ev) => { ev.preventDefault(); showPanel(t.getAttribute('href').slice(1)); }));
    window.addEventListener('hashchange', () => showPanel(location.hash.slice(1)));
    showPanel(location.hash.slice(1));

    baseline = JSON.stringify(collectConfig(true));
    refreshDirty = () => {
      const dirty = JSON.stringify(collectConfig(true)) !== baseline;
      saveBtn.disabled = !dirty;
      refilterBtn.disabled = !dirty;
      const state = $('.save-state', bar);
      if (dirty) { state.textContent = 'Unsaved changes'; state.className = 'save-state muted small'; }
      else if (state.className.includes('muted')) state.textContent = '';
    };
    refreshDirty();
    ['input', 'change', 'click', 'keyup'].forEach((type) => document.addEventListener(type, (ev) => {
      if (ev.target.closest && ev.target.closest('[data-card]')) setTimeout(refreshDirty, 0);
    }));
  }

  // ---------- Job matches: filters apply as you choose (spec 23) ----------
  const filterForm = document.querySelector('form.filterbar');
  const resultsBox = document.getElementById('jobs-results');
  if (filterForm && resultsBox) {
    let timer = null;
    let inflight = null;
    const refresh = async () => {
      const params = new URLSearchParams(new FormData(filterForm));
      Array.from(params.keys()).forEach((k) => { if (params.get(k) === '') params.delete(k); });
      const url = '/jobs?' + params.toString();
      if (inflight) inflight.abort();
      inflight = new AbortController();
      resultsBox.classList.add('loading');
      try {
        const res = await fetch(url, { signal: inflight.signal });
        if (!res.ok) throw new Error('bad response');
        const doc = new DOMParser().parseFromString(await res.text(), 'text/html');
        const fresh = doc.getElementById('jobs-results');
        if (!fresh) throw new Error('no results area');
        resultsBox.innerHTML = fresh.innerHTML;
        const count = resultsBox.querySelector('p.muted');
        const live = document.getElementById('jobs-live');
        if (live && count) live.textContent = count.textContent.trim();
        history.replaceState(null, '', url);
      } catch (err) {
        if (err.name !== 'AbortError') location.href = url; // fall back to a normal page load
      } finally {
        resultsBox.classList.remove('loading');
      }
    };
    const syncActive = () => {
      filterForm.querySelectorAll('.fb-sel').forEach((l) => {
        const sel = l.querySelector('select');
        if (sel && !l.classList.contains('fb-sort')) l.classList.toggle('on', sel.value !== '');
      });
      filterForm.querySelectorAll('.fb-chip').forEach((l) => {
        l.classList.toggle('on', l.querySelector('input').checked);
      });
    };
    const clearControl = (name) => {
      const el = filterForm.elements[name];
      if (!el) return;
      if (el.type === 'checkbox') el.checked = false; else el.value = '';
    };
    document.addEventListener('click', (ev) => {
      const one = ev.target.closest('[data-clear]');
      const all = ev.target.closest('[data-clear-all]');
      if (!one && !all) return;
      (all ? ['q', 'source', 'fresh', 'min_score', 'mode', 'fav'] : [one.dataset.clear]).forEach(clearControl);
      syncActive();
      clearTimeout(timer);
      refresh();
      // the chip that was clicked disappears: keep keyboard focus in the filter bar
      const target = all ? filterForm.elements.q : filterForm.elements[one.dataset.clear];
      if (target && target.focus) target.focus();
    });
    filterForm.addEventListener('submit', (ev) => { ev.preventDefault(); clearTimeout(timer); refresh(); });
    filterForm.addEventListener('change', (ev) => {
      syncActive();
      if (ev.target.matches('input[type=search], input[type=number]')) return; // handled while typing
      clearTimeout(timer);
      refresh();
    });
    filterForm.addEventListener('input', (ev) => {
      if (!ev.target.matches('input[type=search], input[type=number]')) return;
      clearTimeout(timer);
      timer = setTimeout(refresh, 300);
    });
  }

  // ---------- top matches: notice after hiding / not-for-me / applying (spec 22) ----------
  const NOTICE_KEY = 'jh_top_check';
  const notice = document.getElementById('top-notice');

  function showNotice(text, buttonLabel, onClick) {
    if (!notice) return;
    notice.textContent = '';
    const span = document.createElement('span');
    span.textContent = text;
    notice.appendChild(span);
    if (buttonLabel) {
      const btn = document.createElement('button');
      btn.className = 'btn small primary';
      btn.textContent = buttonLabel;
      btn.addEventListener('click', () => { notice.hidden = true; onClick(); });
      notice.appendChild(btn);
    }
    const close = document.createElement('button');
    close.className = 'icon-btn';
    close.setAttribute('aria-label', 'Dismiss');
    close.append(svgIcon('x'));
    close.addEventListener('click', () => { notice.hidden = true; });
    notice.appendChild(close);
    notice.hidden = false;
  }

  async function checkTop() {
    try { sessionStorage.removeItem(NOTICE_KEY); } catch (e) { /* ignore */ }
    try {
      const res = await fetch('/api/top');
      if (!res.ok) return;
      const plan = await res.json();
      if (!plan.need) return;
      if (plan.fill_ids.length) {
        const n = plan.fill_ids.length;
        showNotice(
          'Your top ' + plan.target + ' has ' + (plan.target - plan.need) + ' now.',
          'Score ' + n + ' replacement' + (n === 1 ? '' : 's'),
          () => startRun({ id: 'score', jobs: plan.fill_ids }, 'Scoring ' + n + ' replacements', true)
        );
      } else {
        showNotice(
          'Your top ' + plan.target + ' has ' + (plan.target - plan.need) + '. No unscored postings left.',
          'Search for new jobs',
          () => startRun({ id: 'search' }, 'Searching for new jobs', true)
        );
      }
    } catch (e) { /* the board card still shows the same offer */ }
  }

  try { if (sessionStorage.getItem(NOTICE_KEY)) checkTop(); } catch (e) { /* ignore */ }
  document.addEventListener('click', (ev) => {
    const el = ev.target.closest('[data-top-check]');
    if (!el) return;
    try { sessionStorage.setItem(NOTICE_KEY, '1'); } catch (e) { /* ignore */ }
  }, true);

  const nfm = document.getElementById('not-for-me');
  if (nfm) {
    let nfmJob = null;
    document.addEventListener('click', (ev) => {
      const open = ev.target.closest('[data-not-for-me]');
      if (open) {
        nfmJob = open.dataset.notForMe;
        nfm.querySelector('#nfm-what').textContent = open.dataset.title + ' · ' + open.dataset.company;
        nfm.querySelectorAll('input[name="nfm-reason"]').forEach((r) => { r.checked = false; });
        nfm.querySelector('#nfm-note').value = '';
        const link = nfm.querySelector('#nfm-block-link');
        link.href = '/jobs/' + nfmJob;
        nfm.querySelector('#nfm-block').hidden = false;
        nfm.showModal();
      }
      if (ev.target.closest('[data-close-nfm]')) nfm.close();
    });
    nfm.querySelector('#nfm-save').addEventListener('click', async () => {
      const picked = nfm.querySelector('input[name="nfm-reason"]:checked');
      const body = { note: nfm.querySelector('#nfm-note').value };
      if (picked) body.reason = picked.value; else body.reason = 'other';
      try {
        await post('/api/jobs/' + nfmJob + '/ignore', body);
        try { sessionStorage.setItem(NOTICE_KEY, '1'); } catch (e) { /* ignore */ }
        nfm.close();
        reloadHere();
      } catch (err) { toast(err.message); }
    });
  }

  // ---------- theme (light by default; dark only when chosen) ----------
  const themeBtn = document.getElementById('theme-toggle');
  const applyTheme = (t) => {
    if (t === 'dark') document.documentElement.setAttribute('data-theme', 'dark');
    else document.documentElement.removeAttribute('data-theme');
    if (themeBtn) {
      const dark = t === 'dark';
      const useEl = themeBtn.querySelector('use');
      if (useEl) useEl.setAttribute('href', dark ? '#i-sun' : '#i-moon');
      themeBtn.setAttribute('aria-pressed', String(dark));
      themeBtn.setAttribute('aria-label', dark ? 'Light theme' : 'Dark theme');
      themeBtn.title = dark ? 'Light theme' : 'Dark theme';
    }
  };
  let savedTheme = null;
  try { savedTheme = localStorage.getItem('jh_theme'); } catch (e) { /* private mode */ }
  applyTheme(savedTheme);
  if (themeBtn) {
    themeBtn.addEventListener('click', () => {
      const next = document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
      applyTheme(next);
      try { localStorage.setItem('jh_theme', next); } catch (e) { /* ignore */ }
    });
  }

  // ---------- add a posting by hand ----------
  const addDialog = document.getElementById('add-posting');
  if (addDialog) {
    const q = (sel) => addDialog.querySelector(sel);
    const field = (name) => q('[name="' + name + '"]');
    const showText = (el, text) => { el.textContent = text || ''; el.hidden = !text; };
    document.addEventListener('click', (ev) => {
      if (ev.target.closest('[data-open-add]')) { addDialog.showModal(); q('#add-url').focus(); }
      if (ev.target.closest('[data-close-add]')) addDialog.close();
    });
    q('#add-fetch').addEventListener('click', async () => {
      const url = field('url').value.trim();
      const msg = q('#add-fetch-msg');
      if (!url) { msg.className = 'error-text'; showText(msg, 'Paste a link first.'); return; }
      const btn = q('#add-fetch');
      btn.disabled = true; btn.textContent = 'Fetching…'; showText(msg, '');
      try {
        const f = await post('/api/postings/fetch', { url });
        ['title', 'company', 'location', 'salary_min', 'salary_max', 'salary_currency', 'description'].forEach((n) => { if (f[n]) field(n).value = f[n]; });
        if (f.remote && f.remote !== 'unknown') field('remote').value = f.remote;
        if (f.url) field('url').value = f.url;
        q('#add-blocked').hidden = !f.blocked;
        msg.className = 'hint';
        showText(msg, f.title ? 'Filled from the page. Check every field before saving.' : 'The page had little to read: fill in the fields by hand.');
      } catch (err) { msg.className = 'error-text'; showText(msg, err.message + ' You can paste the text instead.'); }
      finally { btn.disabled = false; btn.textContent = 'Fetch details'; }
    });
    q('#add-save').addEventListener('click', async () => {
      const err = q('#add-error');
      showText(err, '');
      const body = {};
      ['url', 'title', 'company', 'location', 'remote', 'salary_min', 'salary_max', 'salary_currency', 'description'].forEach((n) => { body[n] = field(n).value; });
      const btn = q('#add-save');
      btn.disabled = true;
      try { const res = await post('/api/postings', body); location.href = res.url; }
      catch (e) { showText(err, e.message); btn.disabled = false; }
    });
  }

  // ---------- overflow menus (<details class="more">) ----------
  document.addEventListener('click', (ev) => {
    $$('details.more[open]').forEach((d) => { if (!d.contains(ev.target) || ev.target.closest('.menu button')) d.open = false; });
  });
  document.addEventListener('keydown', (ev) => {
    if (ev.key !== 'Escape') return;
    const open = $('details.more[open]');
    if (open) { open.open = false; $('summary', open).focus(); }
  });

  // ---------- health ----------
  const health = $('#health');
  if (health) {
    fetch('/api/health').then((r) => r.json()).then((checks) => {
      health.innerHTML = '';
      const bad = checks.filter((c) => !c.ok);
      const card = $('#health-card');
      if (card) card.hidden = !bad.some((c) => c.required);  // Home: only when something required fails
      if (!bad.length) {
        const li = document.createElement('li');
        li.innerHTML = '<span class="dot"></span>';
        li.append(document.createTextNode('Everything looks good: ' + checks.map((c) => c.name).join(', ') + '.'));
        health.append(li);
        return;
      }
      checks.forEach((c) => {
        const li = document.createElement('li');
        const dot = document.createElement('span');
        dot.className = 'dot ' + (c.ok ? '' : c.required ? 'bad' : 'warn');
        li.append(dot, document.createTextNode(c.name + ': ' + c.detail));
        health.append(li);
      });
    }).catch(() => (health.textContent = 'Could not run the checks.'));
  }
  // ---------- favorites and company block list ----------
  document.addEventListener('click', async (ev) => {
    const star = ev.target.closest('[data-star]');
    if (star) {
      const on = star.getAttribute('aria-pressed') !== 'true';
      try {
        await post('/api/jobs/' + star.dataset.star + '/favorite', { on });
      } catch (err) { toast(err.message); return; }
      star.setAttribute('aria-pressed', String(on));
      star.classList.toggle('on', on);
      const use = star.querySelector('use');
      if (use) use.setAttribute('href', on ? '#i-star-fill' : '#i-star');
      const note = $('#favorite-note');
      if (note) note.hidden = !on;
      return;
    }
    const noteBtn = ev.target.closest('[data-fav-note]');
    if (noteBtn) {
      const ok = await act(() => post('/api/jobs/' + noteBtn.dataset.favNote + '/favorite', { on: true, note: $('#fav-note').value }), false);
      if (ok) toast('Note saved');
      return;
    }
    const block = ev.target.closest('[data-block-company]');
    if (block) {
      const company = block.dataset.blockCompany;
      if (!confirm('Block ' + company + '? Its postings will be filtered out from now on. You can undo this in Settings.')) return;
      const list = JSON.parse(block.dataset.blocked || '[]').concat([company]);
      const ok = await act(() => post('/api/config', { updates: { search: { companies_exclude: list } } }), false);
      if (!ok) return;
      if (confirm(company + ' is blocked. Re-filter now so its current postings leave your matches?')) startRun({ id: 'refilter' }, 'Re-filtering with your new criteria', true);
      else reloadHere();
    }
  });
})();
