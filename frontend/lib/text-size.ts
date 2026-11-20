export const textSizeScript = `(() => {
  const root = document.documentElement;
  const valid = value => ['small', 'normal', 'large'].includes(value) ? value : 'normal';
  let choice = 'normal';
  try { choice = valid(localStorage.getItem('seoci-text-size')); } catch {}
  const apply = () => { root.dataset.textSize = choice; };
  apply();
  window.addEventListener('seoci-text-size-change', event => {
    choice = valid(event.detail);
    try { localStorage.setItem('seoci-text-size', choice); } catch {}
    apply();
  });
  window.addEventListener('storage', event => {
    if (event.key === 'seoci-text-size' || event.key === null) {
      choice = valid(event.newValue);
      apply();
    }
  });
})();`;
