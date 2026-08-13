(() => {
  const storageKey = 'converter-theme';
  const root = document.documentElement;
  let storedTheme = null;

  try {
    const value = localStorage.getItem(storageKey);
    if (value === 'light' || value === 'dark') storedTheme = value;
  } catch {
    // Storage may be unavailable in hardened/private browser contexts.
  }

  const theme = storedTheme || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
  root.dataset.theme = theme;
  root.style.colorScheme = theme;

  const themeColor = document.querySelector('meta[name="theme-color"]');
  if (themeColor) themeColor.content = theme === 'dark' ? '#171717' : '#ffffff';
})();
