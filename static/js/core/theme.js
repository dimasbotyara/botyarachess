// Theme manager: 20 site themes, per-theme accent palettes, independent
// board color schemes, plus font size / motion / board size helpers.
const STORAGE_KEY = 'botyarachess.theme';
const ACCENT_KEY = 'botyarachess.accent';
const BOARD_KEY = 'botyarachess.board';

/** Swatch palettes mirror themes.css; accents are unique per theme. */
export const THEMES = [
  {
    id: 'catppuccin-latte', group: 'Catppuccin', dark: false,
    colors: { bg: '#eff1f5', surface: '#ffffff', text: '#4c4f69', accent: '#7287fd', boardLight: '#f2dcbe', boardDark: '#b3845c' },
    accents: [
      { id: 'lavender', color: '#7287fd' }, { id: 'blue', color: '#1e66f5' },
      { id: 'mauve', color: '#8839ef' }, { id: 'pink', color: '#ea76cb' },
      { id: 'red', color: '#d20f39' }, { id: 'green', color: '#40a02b' },
      { id: 'teal', color: '#179299' }, { id: 'yellow', color: '#df8e1d' },
      { id: 'peach', color: '#fe640b' },
    ],
  },
  {
    id: 'catppuccin-frappe', group: 'Catppuccin', dark: true,
    colors: { bg: '#303446', surface: '#232634', text: '#c6d0f5', accent: '#8caaee', boardLight: '#a3a9c4', boardDark: '#444a67' },
    accents: [
      { id: 'blue', color: '#8caaee' }, { id: 'lavender', color: '#babbf1' },
      { id: 'sapphire', color: '#7371e4' }, { id: 'teal', color: '#81c8be' },
      { id: 'green', color: '#a6d189' }, { id: 'yellow', color: '#e5c890' },
      { id: 'peach', color: '#ef9f76' }, { id: 'red', color: '#e78284' },
      { id: 'pink', color: '#f4b8e4' }, { id: 'mauve', color: '#ca9ee6' },
    ],
  },
  {
    id: 'catppuccin-macchiato', group: 'Catppuccin', dark: true,
    colors: { bg: '#24273a', surface: '#181926', text: '#cad3f5', accent: '#8bd5ca', boardLight: '#a2a6c3', boardDark: '#3c405c' },
    accents: [
      { id: 'teal', color: '#8bd5ca' }, { id: 'blue', color: '#8aadf4' },
      { id: 'lavender', color: '#b7bdf8' }, { id: 'sapphire', color: '#7dc4e4' },
      { id: 'green', color: '#a6da95' }, { id: 'yellow', color: '#eed49f' },
      { id: 'peach', color: '#f5a97f' }, { id: 'red', color: '#ed8796' },
      { id: 'pink', color: '#f5bde6' }, { id: 'mauve', color: '#c6a0f6' },
    ],
  },
  {
    id: 'catppuccin-mocha', group: 'Catppuccin', dark: true,
    colors: { bg: '#1e1e2e', surface: '#11111b', text: '#cdd6f4', accent: '#f5c2e7', boardLight: '#a7a3c4', boardDark: '#454263' },
    accents: [
      { id: 'pink', color: '#f5c2e7' }, { id: 'mauve', color: '#cba6f7' },
      { id: 'lavender', color: '#b4befe' }, { id: 'blue', color: '#89b4fa' },
      { id: 'sapphire', color: '#74c7ec' }, { id: 'teal', color: '#94e2d5' },
      { id: 'green', color: '#a6e3a1' }, { id: 'yellow', color: '#f9e2af' },
      { id: 'peach', color: '#fab387' }, { id: 'red', color: '#f38ba8' },
    ],
  },
  {
    id: 'gruvbox-dark', group: 'Gruvbox', dark: true,
    colors: { bg: '#282828', surface: '#32302f', text: '#ebdbb2', accent: '#fabd2f', boardLight: '#c4b48c', boardDark: '#705c43' },
    accents: [
      { id: 'yellow', color: '#fabd2f' }, { id: 'orange', color: '#fe8019' },
      { id: 'red', color: '#fb4934' }, { id: 'purple', color: '#d3869b' },
      { id: 'blue', color: '#83a598' }, { id: 'aqua', color: '#8ec07c' },
      { id: 'green', color: '#b8bb26' },
    ],
  },
  {
    id: 'gruvbox-material', group: 'Gruvbox', dark: true,
    colors: { bg: '#282828', surface: '#32302f', text: '#d4be98', accent: '#a9b665', boardLight: '#cfc296', boardDark: '#6e7350' },
    accents: [
      { id: 'green', color: '#a9b665' }, { id: 'yellow', color: '#d8a657' },
      { id: 'orange', color: '#e78a4e' }, { id: 'red', color: '#ea6962' },
      { id: 'aqua', color: '#89b482' }, { id: 'blue', color: '#7daea3' },
      { id: 'purple', color: '#d3869b' },
    ],
  },
  {
    id: 'ayu-dark', group: 'Ayu', dark: true,
    colors: { bg: '#0b0e14', surface: '#11151c', text: '#bfbdb6', accent: '#e6b450', boardLight: '#848e9e', boardDark: '#303743' },
    accents: [
      { id: 'gold', color: '#e6b450' }, { id: 'orange', color: '#ff8f40' },
      { id: 'red', color: '#f26d78' }, { id: 'green', color: '#aad94c' },
      { id: 'blue', color: '#59c2ff' }, { id: 'purple', color: '#d2a6ff' },
      { id: 'grey', color: '#8a919f' },
    ],
  },
  {
    id: 'ayu-light', group: 'Ayu', dark: false,
    colors: { bg: '#fafafa', surface: '#ffffff', text: '#57566e', accent: '#fa8d3e', boardLight: '#f0e6d2', boardDark: '#a98e68' },
    accents: [
      { id: 'orange', color: '#fa8d3e' }, { id: 'yellow', color: '#f2ae49' },
      { id: 'red', color: '#f07171' }, { id: 'green', color: '#86b300' },
      { id: 'blue', color: '#399ee6' }, { id: 'purple', color: '#a37acc' },
      { id: 'grey', color: '#8a9199' },
    ],
  },
  {
    id: 'classic-light', group: 'Classic', dark: false,
    colors: { bg: '#f5f5f4', surface: '#ffffff', text: '#1f2328', accent: '#2f6fed', boardLight: '#f0d9b5', boardDark: '#b58863' },
    accents: [
      { id: 'blue', color: '#2f6fed' }, { id: 'indigo', color: '#6610f2' },
      { id: 'teal', color: '#0d9488' }, { id: 'green', color: '#2da44e' },
      { id: 'amber', color: '#bf8700' }, { id: 'red', color: '#cf222e' },
      { id: 'slate', color: '#57606a' },
    ],
  },
  {
    id: 'classic-dark', group: 'Classic', dark: true,
    colors: { bg: '#16181d', surface: '#20242b', text: '#e3e5ea', accent: '#4f8cff', boardLight: '#f0d9b5', boardDark: '#b58863' },
    accents: [
      { id: 'blue', color: '#4f8cff' }, { id: 'indigo', color: '#8f6bff' },
      { id: 'teal', color: '#2dd4bf' }, { id: 'green', color: '#3fb950' },
      { id: 'amber', color: '#d29922' }, { id: 'red', color: '#f85149' },
      { id: 'pink', color: '#ec6a9c' },
    ],
  },
  {
    id: 'dracula', group: 'Dracula', dark: true,
    colors: { bg: '#282a36', surface: '#1e1f29', text: '#f8f8f2', accent: '#bd93f9', boardLight: '#a5a6c5', boardDark: '#3e4058' },
    accents: [
      { id: 'purple', color: '#bd93f9' }, { id: 'pink', color: '#ff79c6' },
      { id: 'green', color: '#50fa7b' }, { id: 'cyan', color: '#8be9fd' },
      { id: 'yellow', color: '#f1fa8c' }, { id: 'orange', color: '#ffb86c' },
      { id: 'red', color: '#ff5555' },
    ],
  },
  {
    id: 'nord', group: 'Nord', dark: true,
    colors: { bg: '#2e3440', surface: '#3b4252', text: '#eceff4', accent: '#88c0d0', boardLight: '#c2c9d6', boardDark: '#4e5875' },
    accents: [
      { id: 'frost', color: '#88c0d0' }, { id: 'blue', color: '#5e81ac' },
      { id: 'red', color: '#bf616a' }, { id: 'green', color: '#a3be8c' },
      { id: 'yellow', color: '#ebcb8b' }, { id: 'purple', color: '#b48ead' },
      { id: 'orange', color: '#d08770' },
    ],
  },
  {
    id: 'rose-pine', group: 'Rosé Pine', dark: true,
    colors: { bg: '#191724', surface: '#1f1d2e', text: '#e0def4', accent: '#c4a7e7', boardLight: '#8a7f9e', boardDark: '#2e2952' },
    accents: [
      { id: 'iris', color: '#c4a7e7' }, { id: 'foam', color: '#9ccfd8' },
      { id: 'rose', color: '#ebbcba' }, { id: 'gold', color: '#f6c177' },
      { id: 'pine', color: '#31748f' }, { id: 'love', color: '#eb6f92' },
      { id: 'muted', color: '#908caa' },
    ],
  },
  {
    id: 'rose-pine-dawn', group: 'Rosé Pine', dark: false,
    colors: { bg: '#faf4ed', surface: '#fffaf3', text: '#575279', accent: '#907aa9', boardLight: '#f2e2cf', boardDark: '#c9a97e' },
    accents: [
      { id: 'iris', color: '#907aa9' }, { id: 'foam', color: '#56949f' },
      { id: 'rose', color: '#d7827e' }, { id: 'gold', color: '#ea9d34' },
      { id: 'pine', color: '#286983' }, { id: 'love', color: '#b4637a' },
      { id: 'muted', color: '#797593' },
    ],
  },
  {
    id: 'tokyo-night', group: 'Tokyo Night', dark: true,
    colors: { bg: '#1a1b26', surface: '#16161e', text: '#c0caf5', accent: '#7aa2f7', boardLight: '#8b8fc7', boardDark: '#383c66' },
    accents: [
      { id: 'blue', color: '#7aa2f7' }, { id: 'cyan', color: '#7dcfff' },
      { id: 'teal', color: '#73daca' }, { id: 'magenta', color: '#bb9af7' },
      { id: 'orange', color: '#ff9e64' }, { id: 'red', color: '#f7768e' },
      { id: 'yellow', color: '#e0af68' }, { id: 'green', color: '#9ece6a' },
    ],
  },
  {
    id: 'tokyo-night-day', group: 'Tokyo Night', dark: false,
    colors: { bg: '#e1e2e7', surface: '#f7f8fa', text: '#3d4a6d', accent: '#2e7de9', boardLight: '#e8e2d4', boardDark: '#a3977c' },
    accents: [
      { id: 'blue', color: '#2e7de9' }, { id: 'cyan', color: '#007197' },
      { id: 'teal', color: '#118c74' }, { id: 'magenta', color: '#9856ff' },
      { id: 'orange', color: '#b15c00' }, { id: 'red', color: '#f52a65' },
      { id: 'green', color: '#485e30' }, { id: 'yellow', color: '#8c6c3e' },
    ],
  },
  {
    id: 'solarized-dark', group: 'Solarized', dark: true,
    colors: { bg: '#002b36', surface: '#073642', text: '#d3d8cf', accent: '#b58900', boardLight: '#d9d0b3', boardDark: '#7a6f56' },
    accents: [
      { id: 'yellow', color: '#b58900' }, { id: 'blue', color: '#268bd2' },
      { id: 'cyan', color: '#2aa198' }, { id: 'green', color: '#859900' },
      { id: 'magenta', color: '#d33682' }, { id: 'orange', color: '#cb4b16' },
      { id: 'red', color: '#dc322f' }, { id: 'violet', color: '#6c71c4' },
    ],
  },
  {
    id: 'solarized-light', group: 'Solarized', dark: false,
    colors: { bg: '#fdf6e3', surface: '#fffbf0', text: '#586e75', accent: '#268bd2', boardLight: '#f5ecd7', boardDark: '#c9b98c' },
    accents: [
      { id: 'blue', color: '#268bd2' }, { id: 'yellow', color: '#b58900' },
      { id: 'cyan', color: '#2aa198' }, { id: 'green', color: '#859900' },
      { id: 'magenta', color: '#d33682' }, { id: 'orange', color: '#cb4b16' },
      { id: 'red', color: '#dc322f' }, { id: 'violet', color: '#6c71c4' },
    ],
  },
  {
    id: 'everforest-dark', group: 'Everforest', dark: true,
    colors: { bg: '#2d353b', surface: '#272e33', text: '#d3c6aa', accent: '#a7c080', boardLight: '#c9b590', boardDark: '#5d6349' },
    accents: [
      { id: 'green', color: '#a7c080' }, { id: 'yellow', color: '#dbbc7f' },
      { id: 'orange', color: '#e69875' }, { id: 'red', color: '#e67e80' },
      { id: 'aqua', color: '#83c092' }, { id: 'blue', color: '#7fbbb3' },
      { id: 'purple', color: '#d699b6' },
    ],
  },
  {
    id: 'everforest-light', group: 'Everforest', dark: false,
    colors: { bg: '#fbf1e6', surface: '#f7efe0', text: '#5c6a72', accent: '#8da101', boardLight: '#e8dfc8', boardDark: '#a89a78' },
    accents: [
      { id: 'green', color: '#8da101' }, { id: 'yellow', color: '#dfa000' },
      { id: 'orange', color: '#f57d17' }, { id: 'red', color: '#f85552' },
      { id: 'aqua', color: '#35a77c' }, { id: 'blue', color: '#3a94c5' },
      { id: 'purple', color: '#df69ba' },
    ],
  },
];

/** Independent board color schemes ("auto" follows the site theme). */
export const BOARD_THEMES = [
  { id: 'auto', name: 'auto' },
  { id: 'brown', light: '#f0d9b5', dark: '#b58863' },
  { id: 'green', light: '#eeeee2', dark: '#769656' },
  { id: 'blue', light: '#dee3e6', dark: '#8ca2ad' },
  { id: 'ice', light: '#e8f0f2', dark: '#9fb8c2' },
  { id: 'purple', light: '#e5daf0', dark: '#8f7aae' },
  { id: 'red', light: '#f0dcc8', dark: '#c26a5a' },
  { id: 'wood', light: '#d8ab7a', dark: '#9b6b3f' },
  { id: 'marble', light: '#eceae4', dark: '#b6b3ab' },
  { id: 'slate', light: '#c6cede', dark: '#5b6b8c' },
  { id: 'sand', light: '#eadfc4', dark: '#b09868' },
  { id: 'ocean', light: '#dce8ee', dark: '#5f8ca8' },
  { id: 'night', light: '#5c5c7e', dark: '#2e2e44' },
  { id: 'neon', light: '#3d3d5c', dark: '#1c1c30' },
];

const DEFAULT_THEME = 'classic-dark';

let current = DEFAULT_THEME;
let currentAccent = '';
let currentBoard = 'auto';
let serverSync = null;

export function registerServerSync(fn) { serverSync = fn; }
export function currentTheme() { return current; }
export function currentAccentId() { return currentAccent; }
export function currentBoardTheme() { return currentBoard; }

export function isDark() {
  const meta = THEMES.find((th) => th.id === current);
  return meta ? meta.dark : true;
}

export function themeById(id) {
  return THEMES.find((th) => th.id === id) || null;
}

function luminance(hex) {
  const rgb = hex.replace('#', '');
  const r = parseInt(rgb.slice(0, 2), 16) / 255;
  const g = parseInt(rgb.slice(2, 4), 16) / 255;
  const b = parseInt(rgb.slice(4, 6), 16) / 255;
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function root() {
  return document.documentElement;
}

function persist(key, value) {
  localStorage.setItem(key, value);
  if (serverSync) serverSync();
}

/** Apply theme + stored accent (accents are theme-specific). */
export function applyTheme(id, { persist = true, notify = true } = {}) {
  current = THEMES.some((th) => th.id === id) ? id : DEFAULT_THEME;
  root().dataset.theme = current;
  const theme = themeById(current);
  if (theme && theme.accents?.length && !theme.accents.some((a) => a.id === currentAccent)) {
    currentAccent = '';
    localStorage.removeItem(ACCENT_KEY);
  }
  applyAccent(currentAccent);
  if (persist) localStorage.setItem(STORAGE_KEY, current);
  if (persist && serverSync) serverSync();
  if (notify) window.dispatchEvent(new CustomEvent('themechange', { detail: current }));
}

/** Accent color for the active theme; '' resets to the theme default. */
export function applyAccent(accentId) {
  currentAccent = accentId || '';
  const theme = themeById(current);
  const accent = theme?.accents?.find((a) => a.id === currentAccent);
  const style = root().style;
  if (accent) {
    const on = luminance(accent.color) > 0.55 ? '#1a1c22' : '#ffffff';
    style.setProperty('--accent', accent.color);
    style.setProperty('--accent-strong', accent.color);
    style.setProperty('--on-accent', on);
  } else {
    style.removeProperty('--accent');
    style.removeProperty('--accent-strong');
    style.removeProperty('--on-accent');
  }
  if (currentAccent) localStorage.setItem(ACCENT_KEY, currentAccent);
  else localStorage.removeItem(ACCENT_KEY);
}

export function applyBoardTheme(id, { persist = true, notify = true } = {}) {
  currentBoard = BOARD_THEMES.some((b) => b.id === id) ? id : 'auto';
  if (currentBoard === 'auto') delete root().dataset.board;
  else root().dataset.board = currentBoard;
  if (persist) localStorage.setItem(BOARD_KEY, currentBoard);
  if (persist && serverSync) serverSync();
  if (notify) window.dispatchEvent(new CustomEvent('boardchange', { detail: currentBoard }));
}

/** serverSettings: {theme, settings{accent, board_theme,...}} from profile. */
export function initTheme(serverTheme = null, serverSettings = {}) {
  const storedTheme = localStorage.getItem(STORAGE_KEY);
  applyTheme(storedTheme || serverTheme || DEFAULT_THEME, { persist: false, notify: false });

  const storedAccent = localStorage.getItem(ACCENT_KEY);
  const accent = storedAccent ?? serverSettings.accent ?? '';
  if (accent) applyAccent(accent);

  const storedBoard = localStorage.getItem(BOARD_KEY);
  applyBoardTheme(storedBoard ?? serverSettings.board_theme ?? 'auto',
    { persist: false, notify: false });

  applyFontSize(serverSettings.font_size || 'normal');
  applyReduceMotion(serverSettings.reduce_motion);
}

export function applyFontSize(size) {
  const allowed = { small: '13.5px', normal: '15px', large: '16.5px' };
  root().dataset.fontSize = allowed[size] ? size : 'normal';
}

export function applyReduceMotion(flag) {
  root().dataset.reduceMotion = flag ? '1' : '0';
}

export function applyBoardSize(size) {
  root().dataset.boardSize = ['small', 'normal', 'large'].includes(size) ? size : 'normal';
}
