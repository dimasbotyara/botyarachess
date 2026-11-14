// i18n: RU/EN dictionaries, browser auto-detection, DOM application.
import { en } from './locales/en.js';
import { ru } from './locales/ru.js';

const DICTS = { en, ru };
const STORAGE_KEY = 'botyarachess.lang';

let currentLang = 'en';

export function detectLang() {
  for (const lang of navigator.languages || [navigator.language || 'en']) {
    const code = (lang || '').toLowerCase();
    if (code.startsWith('ru')) return 'ru';
    if (code.startsWith('en')) return 'en';
  }
  return 'en';
}

/** serverLocale: explicit choice persisted in the user profile ('' = auto). */
export function initI18n(serverLocale = null) {
  let lang = serverLocale || localStorage.getItem(STORAGE_KEY) || detectLang();
  setLang(lang, { persist: false, notify: false });
}

export function getLang() {
  return currentLang;
}

export function setLang(lang, { persist = true, notify = true } = {}) {
  if (!DICTS[lang]) lang = 'en';
  currentLang = lang;
  document.documentElement.lang = lang;
  if (persist) localStorage.setItem(STORAGE_KEY, lang);
  applyI18n();
  if (notify) window.dispatchEvent(new CustomEvent('langchange', { detail: lang }));
}

export function t(key, params = {}) {
  const dict = DICTS[currentLang] || DICTS.en;
  let template = dict[key] ?? DICTS.en[key] ?? key;
  if (key.startsWith('ai.provider_error|')) {
    template = (dict['ai.provider_error|{msg}'] ?? key).replace('{msg}', key.slice(18));
  }
  return template.replace(/\{(\w+)\}/g, (_, name) =>
    params[name] !== undefined ? String(params[name]) : `{${name}}`);
}

/** Apply translations to elements with data-i18n / data-i18n-ph / data-i18n-title. */
export function applyI18n(root = document) {
  root.querySelectorAll('[data-i18n]').forEach((el) => {
    el.textContent = t(el.dataset.i18n, el.dataset.i18nParams
      ? JSON.parse(el.dataset.i18nParams) : {});
  });
  root.querySelectorAll('[data-i18n-ph]').forEach((el) => {
    el.placeholder = t(el.dataset.i18nPh);
  });
  root.querySelectorAll('[data-i18n-title]').forEach((el) => {
    el.title = t(el.dataset.i18nTitle);
  });
}
