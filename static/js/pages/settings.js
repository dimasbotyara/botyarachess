// Settings page: tabs with appearance (themes+accents), board, language,
// AI providers, security (password / account deletion) and system info.
import { THEMES, BOARD_THEMES, currentTheme, currentAccentId, currentBoardTheme,
         applyTheme, applyAccent, applyBoardTheme, applyFontSize,
         applyReduceMotion, applyBoardSize, themeById } from '../core/theme.js';
import { t, setLang, initI18n, applyI18n } from '../core/i18n.js';
import { api } from '../core/api.js';
import { el, toast, toastError, confirmModal, copyText } from '../core/ui.js';
import { icon } from '../core/icons.js';
import { setVolume, sounds } from '../core/sounds.js';

const body = document.body;
const isAuth = body.dataset.auth === '1';
let profile = {};
try { profile = JSON.parse(body.dataset.settings || '{}'); } catch { /* */ }

function withIcon(name) {
  const span = el('span');
  span.innerHTML = icon(name);
  return span;
}

function persistSettings(patch) {
  if (!isAuth) return;
  api('/api/settings', { method: 'POST', body: { settings: patch } }).catch(() => {});
}

// ------------------------------------------------------------------- tabs
document.querySelectorAll('#settings-tabs .tab').forEach((tab) => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('#settings-tabs .tab').forEach((tb) => tb.classList.remove('active'));
    document.querySelectorAll('.settings-section').forEach((sec) => sec.classList.remove('active'));
    tab.classList.add('active');
    document.querySelector(`.settings-section[data-section="${tab.dataset.tab}"]`)
      ?.classList.add('active');
  });
});

// ----------------------------------------------------------- site themes
const grid = document.getElementById('theme-grid');
function renderThemeGrid() {
  if (!grid) return;
  grid.innerHTML = '';
  for (const theme of THEMES) {
    const card = el(`button.theme-card${theme.id === currentTheme() ? ' selected' : ''}`, {
      onclick: () => {
        applyTheme(theme.id);
        persistSettings({ accent: currentAccentId() });
        renderThemeGrid();
        renderAccentRow();
      },
    });
    const board = el('div.theme-board');
    [theme.colors.boardLight, theme.colors.boardDark,
      theme.colors.boardDark, theme.colors.boardLight].forEach((color) => {
      board.append(el('span', { style: `background:${color}` }));
    });
    card.append(
      board,
      el('div.theme-swatch', {},
        el('span', { style: `background:${theme.colors.bg}` }),
        el('span', { style: `background:${theme.colors.surface}` }),
        el('span', { style: `background:${theme.colors.accent}` }),
        el('span', { style: `background:${theme.colors.text}` }),
      ),
      el('div.t-name', {}, t('theme.' + theme.id)),
      el('div.t-sub', {}, `${theme.group} · ${t(theme.dark ? 'theme.dark' : 'theme.light')}`),
    );
    grid.append(card);
  }
}
renderThemeGrid();

// ---------------------------------------------------------------- accents
const accentRow = document.getElementById('accent-row');
function renderAccentRow() {
  if (!accentRow) return;
  accentRow.innerHTML = '';
  const theme = themeById(currentTheme());
  const accents = theme?.accents || [];
  const conic = `conic-gradient(from 180deg, ${
    accents.slice(0, 5).map((a) => a.color).join(',')}, ${accents[0]?.color || '#888'})`;
  accentRow.append(el(`button.qs-accent${currentAccentId() === '' ? ' selected' : ''}`, {
    title: t('settings.accent_default'),
    style: `background:${conic}`,
    onclick: () => { applyAccent(''); persistSettings({ accent: '' }); renderAccentRow(); },
  }));
  for (const accent of accents) {
    accentRow.append(el(`button.qs-accent${currentAccentId() === accent.id ? ' selected' : ''}`, {
      title: accent.id,
      style: `background:${accent.color}`,
      onclick: () => { applyAccent(accent.id); persistSettings({ accent: accent.id }); renderAccentRow(); },
    }));
  }
}
renderAccentRow();

// ------------------------------------------------------------ board themes
const boardGrid = document.getElementById('board-grid');
if (boardGrid) {
  for (const board of BOARD_THEMES) {
    const label = board.id === 'auto' ? t('quick.board_auto') : t('board.' + board.id);
    const card = el(`button.theme-card${board.id === currentBoardTheme() ? ' selected' : ''}`, {
      onclick: () => {
        applyBoardTheme(board.id);
        persistSettings({ board_theme: board.id });
        boardGrid.querySelectorAll('.theme-card').forEach((c) => c.classList.remove('selected'));
        card.classList.add('selected');
      },
    });
    card.append(el('div.theme-board', {},
      el('span', { style: `background:${board.id === 'auto'
        ? (themeById(currentTheme())?.colors.boardLight || '#eee') : board.light}` }),
      el('span', { style: `background:${board.id === 'auto'
        ? (themeById(currentTheme())?.colors.boardDark || '#888') : board.dark}` }),
      el('span', { style: `background:${board.id === 'auto'
        ? (themeById(currentTheme())?.colors.boardDark || '#888') : board.dark}` }),
      el('span', { style: `background:${board.id === 'auto'
        ? (themeById(currentTheme())?.colors.boardLight || '#eee') : board.light}` }),
    ));
    card.append(
      el('div.t-name', {}, label),
      el('div.t-sub', {}, board.id === 'auto' ? t('quick.board_auto') : board.id),
    );
    boardGrid.append(card);
  }
}

// --------------------------------------------------------- font / motion
const fontSelect = document.getElementById('font-size');
if (fontSelect) {
  fontSelect.value = profile.font_size || 'normal';
  fontSelect.addEventListener('change', () => {
    applyFontSize(fontSelect.value);
    persistSettings({ font_size: fontSelect.value });
  });
}
const motionInput = document.getElementById('reduce-motion');
if (motionInput) {
  motionInput.checked = !!profile.reduce_motion;
  motionInput.addEventListener('change', () => {
    applyReduceMotion(motionInput.checked);
    persistSettings({ reduce_motion: motionInput.checked });
  });
}

// --------------------------------------------------------- board controls
const boardSizeSelect = document.getElementById('board-size');
if (boardSizeSelect) {
  boardSizeSelect.value = profile.board_size || 'normal';
  boardSizeSelect.addEventListener('change', () => {
    applyBoardSize(boardSizeSelect.value);
    persistSettings({ board_size: boardSizeSelect.value });
  });
}

function buildToggleRow({ key, iconName, titleKey, descKey, onChange, initial }) {
  const input = document.createElement('input');
  input.type = 'checkbox';
  input.checked = !!initial;
  input.addEventListener('change', () => {
    onChange(input.checked);
    persistSettings({ [key]: input.checked });
    toast(t('settings.saved'), 'success', 1200);
  });
  return el('div.toggle-row', {},
    withIcon(iconName),
    el('div.t-info', {},
      el('strong', { 'data-i18n': titleKey }, t(titleKey)),
      el('span', { 'data-i18n': descKey }, t(descKey)),
    ),
    el('label.switch', {}, input, el('span.slider')),
  );
}

const boardToggles = document.getElementById('board-toggles');
if (boardToggles) {
  for (const [key, iconName, titleKey, descKey, extra] of [
    ['coords', 'map-pin', 'settings.coords', 'settings.coords_desc', null],
    ['highlight_legal', 'lightbulb', 'settings.highlight', 'settings.highlight_desc', null],
    ['show_captured', 'eye', 'settings.show_captured', 'settings.show_captured_desc',
      (v) => { document.body.dataset.hideCaptured = v ? '' : '1'; }],
    ['autoflip', 'rotate-ccw', 'settings.autoflip', 'settings.autoflip_desc', null],
  ]) {
    boardToggles.append(buildToggleRow({
      key, iconName, titleKey, descKey,
      initial: profile[key] ?? true,
      onChange: (v) => extra?.(v),
    }));
  }
  applyI18n(boardToggles);
}

const soundToggles = document.getElementById('sound-toggles');
if (soundToggles) {
  soundToggles.append(buildToggleRow({
    key: 'sounds', iconName: 'volume-2',
    titleKey: 'settings.sounds', descKey: 'settings.sounds_desc',
    initial: profile.sounds ?? true,
    onChange: () => sounds.move(),
  }));
  applyI18n(soundToggles);
}

const volumeInput = document.getElementById('volume');
if (volumeInput) {
  volumeInput.value = profile.volume ?? 70;
  volumeInput.addEventListener('input', () => {
    setVolume(Number(volumeInput.value));
  });
  volumeInput.addEventListener('change', () => {
    persistSettings({ volume: Number(volumeInput.value) });
    sounds.move();
  });
}

// ---------------------------------------------------------------- language
const langRadios = document.querySelectorAll('[name="lang-choice"]');
function markLang() {
  const active = (body.dataset.locale || '').trim()
    || localStorage.getItem('botyarachess.lang') || 'auto';
  langRadios.forEach((radio) => { radio.checked = radio.value === active; });
}
markLang();
langRadios.forEach((radio) => {
  radio.addEventListener('change', async () => {
    const value = radio.value;
    if (value === 'auto') {
      localStorage.removeItem('botyarachess.lang');
      initI18n(null);
    } else {
      localStorage.setItem('botyarachess.lang', value);
      setLang(value);
    }
    body.dataset.locale = value === 'auto' ? '' : value;
    if (isAuth) {
      await api('/api/settings', {
        method: 'POST', body: { locale: value === 'auto' ? '' : value },
      }).catch(() => {});
    }
    toast(t('settings.saved'), 'success', 1500);
  });
});

// ------------------------------------------------------------- AI settings
const PROVIDER_FIELDS = {
  manual: [],
  openai: ['model', 'api_key'],
  anthropic: ['model', 'api_key'],
  gemini: ['model', 'api_key'],
  lmstudio: ['lm_host', 'lm_port', 'model'],
  compat: ['base_url', 'model', 'api_key'],
};

let savedAi = {};
try {
  savedAi = JSON.parse(document.getElementById('settings-root')?.dataset.ai || '{}');
} catch { /* */ }

const aiProvider = document.getElementById('ai-provider');
const aiPersona = document.getElementById('ai-persona');
const aiForm = document.getElementById('ai-form');
const testBtn = document.getElementById('btn-ai-test');
const testResult = document.getElementById('ai-test-result');

function fillAiForm() {
  if (!aiProvider) return;
  aiProvider.value = savedAi.provider || 'manual';
  document.getElementById('ai-model').value = savedAi.model || '';
  document.getElementById('ai-base-url').value = savedAi.base_url || '';
  document.getElementById('ai-lm-host').value = savedAi.lm_host || '';
  document.getElementById('ai-lm-port').value = savedAi.lm_port || 1234;
  document.getElementById('ai-persona').value = savedAi.persona || 'coach';
  document.getElementById('ai-persona-custom').value = savedAi.persona_custom || '';
  document.getElementById('ai-chat-enabled').checked = savedAi.chat_enabled !== false;
  document.getElementById('ai-temperature').value = savedAi.temperature ?? 0.7;
  const hint = document.getElementById('key-hint');
  if (savedAi.api_key_set && hint) hint.textContent = t('settings.ai_key_set');
}
fillAiForm();

function refreshProviderFields() {
  const active = PROVIDER_FIELDS[aiProvider?.value || 'manual'] || [];
  aiForm?.querySelectorAll('[data-field]').forEach((field) => {
    field.classList.toggle('hidden', !active.includes(field.dataset.field));
  });
  document.getElementById('persona-custom-wrap')?.classList.toggle(
    'hidden', aiPersona?.value !== 'custom');
}
aiProvider?.addEventListener('change', refreshProviderFields);
aiPersona?.addEventListener('change', refreshProviderFields);
refreshProviderFields();

aiForm?.addEventListener('submit', async (e) => {
  e.preventDefault();
  const data = {
    provider: aiProvider?.value ?? 'manual',
    model: document.getElementById('ai-model')?.value ?? '',
    base_url: document.getElementById('ai-base-url')?.value ?? '',
    lm_host: document.getElementById('ai-lm-host')?.value ?? '',
    lm_port: document.getElementById('ai-lm-port')?.value ?? '1234',
    api_key: document.getElementById('ai-key')?.value ?? '',
    persona: aiPersona?.value ?? 'coach',
    persona_custom: document.getElementById('ai-persona-custom')?.value ?? '',
    chat_enabled: document.getElementById('ai-chat-enabled')?.checked ?? true,
    temperature: document.getElementById('ai-temperature')?.value ?? '0.7',
  };
  try {
    const result = await api('/api/settings/ai', { method: 'POST', body: data });
    savedAi = result.ai || savedAi;
    document.getElementById('ai-key').value = '';
    fillAiForm();
    refreshProviderFields();
    toast(t('settings.saved'), 'success');
  } catch (error) { toastError(error); }
});

testBtn?.addEventListener('click', async () => {
  testBtn.disabled = true;
  testResult.textContent = t('settings.testing');
  try {
    const data = {
      provider: aiProvider?.value ?? 'manual',
      model: document.getElementById('ai-model')?.value ?? '',
      base_url: document.getElementById('ai-base-url')?.value ?? '',
      lm_host: document.getElementById('ai-lm-host')?.value ?? '',
      lm_port: document.getElementById('ai-lm-port')?.value ?? '1234',
      api_key: document.getElementById('ai-key')?.value ?? '',
    };
    const result = await api('/api/ai/test', { method: 'POST', body: data });
    if (result.ok) {
      testResult.textContent = `${t('settings.test_ok')} → ${result.raw}`;
      testResult.style.color = 'var(--success)';
    } else {
      testResult.textContent = `${t('settings.test_fail')}: ${result.error}`;
      testResult.style.color = 'var(--danger)';
    }
  } catch (error) {
    testResult.textContent = `${t('settings.test_fail')}: ${error.message}`;
    testResult.style.color = 'var(--danger)';
  } finally {
    testBtn.disabled = false;
  }
});

// ---------------------------------------------------------------- security
document.getElementById('password-form')?.addEventListener('submit', async (e) => {
  e.preventDefault();
  try {
    await api('/api/security/password', {
      method: 'POST',
      body: {
        current: document.getElementById('pw-current').value,
        new: document.getElementById('pw-new').value,
      },
    });
    document.getElementById('pw-current').value = '';
    document.getElementById('pw-new').value = '';
    toast(t('settings.password_changed'), 'success');
  } catch (error) {
    if (error.message === 'wrong_current_password') toastError(t('settings.wrong_current_password'));
    else toastError(error);
  }
});

document.getElementById('btn-delete-account')?.addEventListener('click', async () => {
  const confirmed = await confirmModal({
    titleKey: 'settings.delete_account', icon: 'trash-2', danger: true,
  });
  if (!confirmed) return;
  const prompt = t('settings.delete_confirm_prompt');
  const typed = window.prompt(`${prompt}\n(${body.dataset.username})`, '');
  if (typed !== body.dataset.username) {
    toast(t('settings.delete_confirm_prompt'), 'error');
    return;
  }
  try {
    await api('/api/security/delete_account', {
      method: 'POST', body: { confirm: typed },
    });
    toast(t('settings.account_deleted'), 'success');
    setTimeout(() => { window.location.href = '/login'; }, 900);
  } catch (error) { toastError(error); }
});

// ------------------------------------------------------------------ system
const engineNode = document.getElementById('engine-status');
if (engineNode) {
  api('/api/engine/status').then((status) => {
    engineNode.innerHTML = status.available
      ? `${icon('check')} ${t('settings.engine_ok', { name: status.name })}`
      : `${icon('triangle-alert')} ${t('settings.engine_none')}`;
    engineNode.style.color = status.available ? 'var(--success)' : 'var(--warning)';
  }).catch(() => {});
}
