// Small vanilla helpers for the local UI: JSON posts, run log polling, health, copy.
(function () {
  const $ = (sel, root) => (root || document).querySelector(sel);
  const $$ = (sel, root) => Array.from((root || document).querySelectorAll(sel));

  function toast(message) {
    const el = $('#toast');
    el.textContent = message;
    el.hidden = false;
    clearTimeout(toast.t);
    toast.t = setTimeout(() => (el.hidden = true), 4000);
  }

  async function post(url, body) {
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body || {}),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || 'Request failed (' + res.status + ')');
    return data;
  }

  async function act(fn, reload) {
    try {
      await fn();
      if (reload !== false) location.reload();
      return true;
    } catch (err) {
      toast(err.message);
      return false;
    }
  }

  document.addEventListener('click', (ev) => {
    const el = ev.target.closest('[data-post]');
    if (el) {
      if (el.dataset.confirm && !confirm(el.dataset.confirm)) return;
      act(() => post(el.dataset.post, JSON.parse(el.dataset.json || '{}')));
      return;
    }
    const copy = ev.target.closest('[data-copy]');
    if (copy) {
      navigator.clipboard.writeText($(copy.dataset.copy).textContent).then(() => toast('Copied'));
      return;
    }
    const notes = ev.target.closest('[data-notes-job]');
    if (notes) {
      act(() => post('/api/jobs/' + notes.dataset.notesJob + '/notes', { notes: $('#notes').value }), false)
        .then((ok) => ok && toast('Notes saved'));
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
    const body = Object.fromEntries(new FormData(form));
    act(() => post('/api/jobs/' + form.dataset.newInterview + '/interviews', body));
  });

  // --- build the package of ONE posting, in place ---
  $$('[data-build-job]').forEach((btn) => {
    btn.addEventListener('click', async () => {
      const box = $('#build-box'), logEl = $('#build-log'), badge = $('#build-status');
      const all = $$('[data-build-job]');
      all.forEach((b) => (b.disabled = true));
      box.hidden = false;
      logEl.textContent = 'Starting…';
      badge.textContent = 'running…';
      badge.className = 'badge warn';
      let run;
      try {
        run = await post('/api/runs', { id: 'tailor', jobs: [parseInt(btn.dataset.buildJob, 10)] });
      } catch (err) {
        badge.textContent = 'not started';
        badge.className = 'badge bad';
        logEl.textContent = err.message;
        all.forEach((b) => (b.disabled = false));
        return;
      }
      logEl.textContent = '';
      const tick = (since) => fetch('/api/runs/' + run.id + '?since=' + since)
        .then((r) => r.json()).then((state) => {
          if (state.log) { logEl.textContent += (logEl.textContent ? '\n' : '') + state.log; logEl.scrollTop = logEl.scrollHeight; }
          if (state.status === 'running') return setTimeout(() => tick(state.next), 1000);
          if (state.status === 'ok') {
            badge.textContent = 'done';
            badge.className = 'badge good';
            setTimeout(() => location.reload(), 900);
          } else {
            badge.textContent = 'failed (exit ' + state.exit_code + ')';
            badge.className = 'badge bad';
            all.forEach((b) => (b.disabled = false));
          }
        }).catch(() => { badge.textContent = 'lost connection'; badge.className = 'badge bad'; });
      tick(0);
    });
  });

  // --- health ---
  const health = $('#health');
  if (health) {
    fetch('/api/health').then((r) => r.json()).then((checks) => {
      health.innerHTML = '';
      checks.forEach((c) => {
        const li = document.createElement('li');
        const dot = document.createElement('span');
        dot.className = 'dot ' + (c.ok ? '' : c.required ? 'bad' : 'warn');
        li.append(dot, document.createTextNode(c.name + ': ' + c.detail));
        health.append(li);
      });
    }).catch(() => (health.textContent = 'Could not run the checks.'));
  }

  // --- run page ---
  const log = $('#log');
  if (log) {
    const status = $('#run-status');
    let timer = null;

    function setStatus(text, cls) {
      status.textContent = text;
      status.className = 'badge ' + (cls || '');
    }

    function poll(id, since) {
      fetch('/api/runs/' + id + '?since=' + since).then((r) => r.json()).then((run) => {
        if (run.log) { log.textContent += (log.textContent ? '\n' : '') + run.log; log.scrollTop = log.scrollHeight; }
        if (run.status === 'running') {
          setStatus('running…', 'warn');
          timer = setTimeout(() => poll(id, run.next), 1000);
        } else {
          setStatus(run.status === 'ok' ? 'finished' : 'failed (exit ' + run.exit_code + ')', run.status === 'ok' ? 'good' : 'bad');
          $$('[data-run]').forEach((b) => (b.disabled = false));
        }
      }).catch(() => setStatus('lost connection', 'bad'));
    }

    $$('[data-run]').forEach((btn) => {
      btn.addEventListener('click', async () => {
        const card = btn.closest('.runcard');
        const opt = (name) => $('[data-opt=' + name + ']', card);
        const body = { id: btn.dataset.run };
        if (opt('dry_run')) body.dry_run = opt('dry_run').checked;
        if (opt('force')) body.force = opt('force').checked;
        if (opt('limit') && opt('limit').value) body.limit = parseInt(opt('limit').value, 10);
        if (opt('jobs') && opt('jobs').value.trim()) {
          body.jobs = opt('jobs').value.split(/[\s,]+/).filter(Boolean).map((v) => parseInt(v, 10));
          if (body.jobs.some(Number.isNaN)) return toast('Posting ids must be numbers');
        }
        try {
          const run = await post('/api/runs', body);
          log.textContent = '';
          $$('[data-run]').forEach((b) => (b.disabled = true));
          setStatus('running…', 'warn');
          clearTimeout(timer);
          poll(run.id, 0);
        } catch (err) { toast(err.message); }
      });
    });

    const query = new URLSearchParams(location.search);
    const preset = query.get('tailor');
    if (preset) {
      const card = $('[data-spec=tailor]');
      $('[data-opt=jobs]', card).value = preset;
      if (query.get('force')) $('[data-opt=force]', card).checked = true;
      card.scrollIntoView({ behavior: 'smooth', block: 'center' });
      if (query.get('autorun')) $('[data-run=tailor]', card).click();
    }
  }
})();
