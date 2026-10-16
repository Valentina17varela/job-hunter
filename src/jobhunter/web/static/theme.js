// Applies the saved theme before the page paints (no flash). Light is the default.
// The toggle in app.js writes the same key. Offline, no dependencies.
(function () {
  try {
    if (localStorage.getItem('jh_theme') === 'dark') document.documentElement.setAttribute('data-theme', 'dark');
  } catch (e) { /* storage blocked: stay on the default light theme */ }
})();
