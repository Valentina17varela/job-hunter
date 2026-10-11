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
    if (!res.ok) throw new Error(data.error || 'Request failed (' + res.status + ')');
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
})();
