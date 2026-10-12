// Job Hunter UI helpers: JSON posts, the run dock (live log on any page), health, copy.
(function () {
  const $ = (sel, root) => (root || document).querySelector(sel);
  const $$ = (sel, root) => Array.from((root || document).querySelectorAll(sel));

  function toast(message) {
    const el = $('#toast');
    el.textContent = message;
    el.hidden = false;
    clearTimeout(toast.t);
    toast.t = setTimeout(() => (el.hidden = true), 4500);
  }

  async function post(url, body) {
    const res = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body || {}) });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) { const err = new Error(data.error || 'Request failed (' + res.status + ')'); err.data = data; throw err; }
    return data;
  }

  async function act(fn, reload) {
    try { await fn(); if (reload !== false) location.reload(); return true; }
    catch (err) { toast(err.message); return false; }
  }

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
      if (ok && run.reload) { $('#dock-result').textContent = 'Finished. Updating this page…'; setTimeout(() => location.reload(), 1200); }
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
    $('#dock-refresh').addEventListener('click', () => location.reload());
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
    if (sel) act(() => post('/api/jobs/' + sel.dataset.stageJob + '/stage', { stage: sel.value }));
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
    function render() {
      $$('.tag', box).forEach((t) => t.remove());
      values.forEach((v, i) => {
        const tag = document.createElement('span');
        tag.className = 'tag';
        tag.append(document.createTextNode(v));
        const x = document.createElement('button');
        x.type = 'button';
        x.setAttribute('aria-label', 'Remove ' + v);
        x.textContent = '×';
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
    box.getValues = () => { if (input.value.trim()) add(input.value); return values.slice(); };
    render();
  }
  $$('.tags[data-cfg]').forEach(initTags);

  function readField(el) {
    switch (el.dataset.type) {
      case 'tags': return el.getValues();
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

  document.addEventListener('click', async (ev) => {
    const saveCfg = ev.target.closest('[data-save-cfg]');
    if (saveCfg) {
      const card = saveCfg.closest('[data-card]');
      const state = $('.save-state', saveCfg.closest('.form-actions'));
      if (saveCfg.disabled) return;
      saveCfg.disabled = true;
      const updates = {};
      $$('[data-cfg]', card).forEach((el) => { const v = readField(el); if (v !== undefined) setNested(updates, el.dataset.cfg, v); });
      try {
        await post('/api/config', { updates });
        showErrors(card, []);
        state.textContent = 'Saved ✓';
        state.className = 'save-state ok small';
        if (saveCfg.dataset.then === 'refilter') startRun({ id: 'refilter' }, 'Re-filtering with your new criteria', true);
      } catch (err) {
        let detail = err.message;
        if (err.data && err.data.errors) {
          showErrors(card, err.data.errors);
          detail = err.data.errors.map((e) => e.field + ': ' + e.message).join(' · ');
        }
        state.textContent = 'Not saved: ' + detail;
        state.className = 'save-state bad small';
      } finally { saveCfg.disabled = false; }
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

  $$('#settings-tabs a').forEach((a) => a.addEventListener('click', () => {
    $$('#settings-tabs a').forEach((x) => x.classList.remove('on'));
    a.classList.add('on');
  }));

  // ---------- theme (light by default; dark only when chosen) ----------
  const themeBtn = document.getElementById('theme-toggle');
  const applyTheme = (t) => {
    if (t === 'dark') document.documentElement.setAttribute('data-theme', 'dark');
    else document.documentElement.removeAttribute('data-theme');
    if (themeBtn) themeBtn.textContent = t === 'dark' ? '◑ Light theme' : '◐ Dark theme';
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

  // ---------- health ----------
  const health = $('#health');
  if (health) {
    fetch('/api/health').then((r) => r.json()).then((checks) => {
      health.innerHTML = '';
      const bad = checks.filter((c) => !c.ok);
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
      star.textContent = on ? '★' : '☆';
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
      else location.reload();
    }
  });
})();
