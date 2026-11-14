// Unified quick-settings overlay: theme, accent, board scheme, language.
// Opened from the header sliders button; changes apply instantly and sync
// to the server profile (same persistence the Settings page uses).
import { THEMES, BOARD_THEMES, currentTheme, currentAccentId, currentBoardTheme,
         applyTheme, applyAccent, applyBoardTheme } from './theme.js';
import { t, setLang, initI18n } from './i18n.js';
import { el } from './ui.js';
import { icon } from './icons.js';

const isAuth = () => document.body.dataset.auth === '1';

function persistToServer() {
  if (!isAuth()) return;
  import('./api.js').then(({ api }) => {
    api('/api/settings', {
      method: 'POST',
      body: {
        theme: currentTheme(),
        settings: {
          accent: currentAccentId(),
          board_theme: currentBoardTheme(),
        },
      },
    }).catch(() => {});
  });
}

function chip(label, selected, swatches, onclick) {
  const node = el(`button.qs-chip${selected ? ' selected' : ''}`, { onclick });
  const dots = el('span.qs-dots');
  for (const color of swatches) {
    dots.append(el('span', { style: `background:${color}` }));
  }
  node.append(dots, el('span.qs-label', {}, label));
  return node;
}

function buildContent() {
  const wrap = el('div.qs-overlay-content');
  const theme = THEMES.find((th) => th.id === currentTheme());

  // ------------------------------------------------------------ site theme
  wrap.append(el('div.qs-title', {}, t('common.theme')));
  const themeGrid = el('div.qs-chip-grid');
  for (const th of THEMES) {
    themeGrid.append(chip(
      t('theme.' + th.id),
      th.id === currentTheme(),
      [th.colors.bg, th.colors.surface, th.colors.accent],
      () => { applyTheme(th.id); persistToServer(); rerender(); },
    ));
  }
  wrap.append(themeGrid);

  // ---------------------------------------------------------- accent colors
  if (theme?.accents?.length) {
    wrap.append(el('div.qs-title', {}, t('quick.accent')));
    const accentRow = el('div.qs-accent-row');
    const conic = `conic-gradient(from 180deg, ${
      theme.accents.slice(0, 5).map((a) => a.color).join(',')}, ${theme.accents[0].color})`;
    accentRow.append(el(`button.qs-accent${currentAccentId() === '' ? ' selected' : ''}`, {
      title: t('quick.accent_default'),
      style: `background:${conic}`,
      onclick: () => { applyAccent(''); persistToServer(); rerender(); },
    }));
    for (const accent of theme.accents) {
      accentRow.append(el(`button.qs-accent${currentAccentId() === accent.id ? ' selected' : ''}`, {
        title: accent.id,
        style: `background:${accent.color}`,
        onclick: () => { applyAccent(accent.id); persistToServer(); rerender(); },
      }));
    }
    wrap.append(accentRow);
  }

  // ----------------------------------------------------------- board scheme
  wrap.append(el('div.qs-title', {}, t('quick.board')));
  const boardGrid = el('div.qs-chip-grid');
  for (const board of BOARD_THEMES) {
    const label = board.id === 'auto' ? t('quick.board_auto')
      : t('board.' + board.id);
    boardGrid.append(chip(
      label,
      board.id === currentBoardTheme(),
      board.id === 'auto' ? [theme.colors.boardLight, theme.colors.boardDark]
        : [board.light, board.dark],
      () => { applyBoardTheme(board.id); persistToServer(); rerender(); },
    ));
  }
  wrap.append(boardGrid);

  // -------------------------------------------------------------- language
  wrap.append(el('div.qs-title', {}, t('common.language')));
  const langRow = el('div.qs-lang-row');
  const active = (document.body.dataset.locale || '').trim()
    || localStorage.getItem('botyarachess.lang') || 'auto';
  for (const [code, label] of [['auto', t('settings.auto')], ['en', 'English'],
    ['ru', 'Русский']]) {
    langRow.append(el(`button.qs-lang${active === code ? ' selected' : ''}`, {
      onclick: () => {
        if (code === 'auto') {
          localStorage.removeItem('botyarachess.lang');
          initI18n(null);
        } else {
          localStorage.setItem('botyarachess.lang', code);
          setLang(code);
        }
        document.body.dataset.locale = code === 'auto' ? '' : code;
        if (isAuth()) {
          import('./api.js').then(({ api }) => {
            api('/api/settings', {
              method: 'POST',
              body: { locale: code === 'auto' ? '' : code },
            }).catch(() => {});
          });
        }
        rerender();
      },
    }, label));
  }
  wrap.append(langRow);

  wrap.append(el('a.qs-footer', { href: '/settings' },
    icon('settings'), t('quick.all_settings')));
  return wrap;
}

let backdropEl = null;
let contentHost = null;

function rerender() {
  if (contentHost) {
    contentHost.innerHTML = '';
    contentHost.append(buildContent());
  }
}

export function openQuickSettings() {
  if (backdropEl) { closeQuickSettings(); return; }
  backdropEl = el('div.modal-backdrop.qs-backdrop');
  const panel = el('div.modal.qs-modal');
  const h3 = el('h3', {}, t('quick.title'));
  h3.insertAdjacentHTML('afterbegin', icon('sliders-horizontal'));
  const head = el('div.qs-head', {}, h3);
  const closeBtn = el('button.icon-btn', { 'aria-label': 'Close' });
  closeBtn.innerHTML = icon('x');
  closeBtn.addEventListener('click', closeQuickSettings);
  head.append(closeBtn);
  panel.append(head);

  contentHost = el('div.qs-body');
  contentHost.append(buildContent());
  panel.append(contentHost);
  backdropEl.append(panel);

  backdropEl.addEventListener('pointerdown', (e) => {
    if (e.target === backdropEl) closeQuickSettings();
  });
  document.body.append(backdropEl);
}

export function closeQuickSettings() {
  backdropEl?.remove();
  backdropEl = null;
  contentHost = null;
}

export function initQuickSettings() {
  document.getElementById('quick-settings-btn')
    ?.addEventListener('click', openQuickSettings);
}
