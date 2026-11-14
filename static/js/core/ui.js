// UI helpers: DOM building, toasts, modals, clipboard, clock formatting.
import { icon } from './icons.js';
import { t } from './i18n.js';

/** Tiny DOM builder: el('div.card.highlight', {onclick}, children...).
 * Classes may be separated by dots and/or spaces. */
export function el(selector, attrs = {}, ...children) {
  const [tag = 'div', ...classes] = selector.split(/[.\s]+/).filter(Boolean);
  const node = document.createElement(tag);
  if (classes.length) node.classList.add(...classes);
  for (const [key, value] of Object.entries(attrs)) {
    if (key.startsWith('on') && typeof value === 'function') {
      node.addEventListener(key.slice(2).toLowerCase(), value);
    } else if (key === 'dataset') {
      Object.assign(node.dataset, value);
    } else if (value !== undefined && value !== null) {
      node.setAttribute(key, value);
    }
  }
  for (const child of children.flat()) {
    if (child === null || child === undefined) continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}

export function esc(text) {
  const div = document.createElement('div');
  div.textContent = String(text ?? '');
  return div.innerHTML;
}

// ------------------------------------------------------------------ toasts
let toastIcons = { success: 'check', error: 'triangle-alert', info: 'info' };

export function toast(message, type = 'info', timeout = 3800) {
  const container = document.getElementById('toasts');
  if (!container) return;
  const box = el('div.toast.' + type, { role: 'status' });
  const iconEl = el('span');
  iconEl.innerHTML = icon(toastIcons[type] || 'info');
  box.append(iconEl, el('span', {}, message));
  container.append(box);
  setTimeout(() => {
    box.style.opacity = '0';
    setTimeout(() => box.remove(), 250);
  }, timeout);
}

/** Translate an error key from the server (with optional |param suffix). */
export function toastError(error, fallbackKey = 'common.error') {
  const key = typeof error === 'string' ? error : (error?.message || fallbackKey);
  if (key.includes('|')) {
    const [base, param] = key.split('|');
    toast(t('ai.provider_error|{msg}', { msg: param }).replace('{msg}', param), 'error');
    return;
  }
  toast(t(key, key), 'error');
}

// ------------------------------------------------------------------ modals
export function openModal(contentEl, { dismissible = true } = {}) {
  const backdrop = el('div.modal-backdrop');
  const modal = el('div.modal', { role: 'dialog' }, contentEl);
  backdrop.append(modal);
  document.body.append(backdrop);
  const close = () => backdrop.remove();
  if (dismissible) {
    backdrop.addEventListener('pointerdown', (e) => {
      if (e.target === backdrop) close();
    });
  }
  return { backdrop, modal, close };
}

export function confirmModal({ titleKey, icon: iconName = 'circle-help', danger = false }) {
  return new Promise((resolve) => {
    const content = el('div', {});
    const head = el('span');
    head.innerHTML = icon(iconName, 'result-icon');
    content.append(head, el('h3', {}, t(titleKey)));
    const actions = el('div.modal-actions');
    const cancelBtn = el('button.btn.btn-ghost', { onclick: () => finish(false) }, t('common.cancel'));
    const okBtn = el(`button.btn.${danger ? 'btn-danger' : 'btn-primary'}`,
      { onclick: () => finish(true) }, t('common.confirm'));
    actions.append(cancelBtn, okBtn);
    content.append(actions);
    const { close } = openModal(content, { dismissible: false });
    function finish(result) { close(); resolve(result); }
  });
}

// --------------------------------------------------------------- clipboard
export async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
    toast(t('common.copied'), 'success', 1800);
    return true;
  } catch {
    // fallback for older browsers / non-secure contexts (plain HTTP LAN)
    const area = document.createElement('textarea');
    area.value = text;
    area.style.position = 'fixed';
    area.style.opacity = '0';
    document.body.append(area);
    area.select();
    let ok = false;
    try { ok = document.execCommand('copy'); } catch { ok = false; }
    area.remove();
    if (ok) toast(t('common.copied'), 'success', 1800);
    else toast(t('common.error'), 'error');
    return ok;
  }
}

// ------------------------------------------------------------------ clocks
export function formatClock(ms) {
  const total = Math.max(0, Math.ceil(ms / 1000));
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const seconds = total % 60;
  const mm = String(minutes).padStart(2, '0');
  const ss = String(seconds).padStart(2, '0');
  if (hours > 0) return `${hours}:${mm}:${ss}`;
  return `${mm}:${ss}`;
}
