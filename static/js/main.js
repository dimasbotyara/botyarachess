// Global bootstrap for every page: theme system, language, header menus,
// sound volume and accessibility preferences from the user profile.
import { initTheme, applyTheme, applyAccent, applyBoardTheme, applyFontSize,
         applyReduceMotion, applyBoardSize, registerServerSync, currentTheme,
         currentAccentId, currentBoardTheme } from './core/theme.js';
import { initI18n, setLang, t, getLang } from './core/i18n.js';
import { hydrateIcons } from './core/icons.js';
import { el, toast } from './core/ui.js';
import { api } from './core/api.js';
import { setSoundsEnabled, setVolume, unlockAudio } from './core/sounds.js';
import { initQuickSettings } from './core/quick-settings.js';

const body = document.body;
const isAuth = body.dataset.auth === '1';
let profileSettings = {};
try { profileSettings = JSON.parse(body.dataset.settings || '{}'); } catch { /* */ }

// ----------------------------------------------------------------- i18n/theme
initTheme(body.dataset.theme || null, profileSettings);
initI18n(body.dataset.locale || null);
hydrateIcons();
initQuickSettings();

// local UI-only overrides (mute button on the game page etc.)
setSoundsEnabled(profileSettings.sounds !== false
  && localStorage.getItem('botyarachess.muted') !== '1');
setVolume(profileSettings.volume ?? 70);
applyBoardSize(profileSettings.board_size || 'normal');
if (profileSettings.show_captured === false) {
  body.dataset.hideCaptured = '1';
}
unlockAudio();

if (isAuth) {
  let syncTimer = null;
  registerServerSync(() => {
    // debounce: theme + accent + board clicks can come in bursts
    clearTimeout(syncTimer);
    syncTimer = setTimeout(() => {
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
    }, 400);
  });
}

// ----------------------------------------------------------------- header UI
function closeAllMenus(except = null) {
  document.querySelectorAll('.menu-wrap.open').forEach((wrap) => {
    if (wrap !== except) wrap.classList.remove('open');
  });
}

document.querySelectorAll('[data-menu]').forEach((button) => {
  button.addEventListener('click', (e) => {
    e.stopPropagation();
    const wrap = button.closest('.menu-wrap');
    const opening = !wrap.classList.contains('open');
    closeAllMenus();
    if (opening) wrap.classList.add('open');
  });
});

document.addEventListener('click', () => closeAllMenus());
document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeAllMenus(); });

// hamburger (mobile navigation)
document.getElementById('hamburger')?.addEventListener('click', () => {
  document.querySelector('.nav')?.classList.toggle('open');
});

// flash messages rendered by the server as texts
document.querySelectorAll('.flashes [data-key]').forEach((node) => {
  toast(node.dataset.text || node.dataset.key,
    node.dataset.category === 'error' ? 'error' : 'success');
});
