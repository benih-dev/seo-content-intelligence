export const themeScript = `(() => {
  const root = document.documentElement;
  const media = window.matchMedia('(prefers-color-scheme: dark)');
  const valid = value => ['light', 'dark', 'system'].includes(value) ? value : 'system';
  let choice = 'system';
  try { choice = valid(localStorage.getItem('seoci-theme')); } catch {}
  const apply = () => {
    root.dataset.themePreference = choice;
    root.dataset.theme = choice === 'system' ? (media.matches ? 'dark' : 'light') : choice;
  };
  apply();
  media.addEventListener('change', apply);
  window.addEventListener('seoci-theme-change', event => {
    choice = valid(event.detail);
    try { localStorage.setItem('seoci-theme', choice); } catch {}
    apply();
  });
  window.addEventListener('storage', event => {
    if (event.key === 'seoci-theme' || event.key === null) {
      choice = valid(event.newValue);
      apply();
    }
  });
})();`;
