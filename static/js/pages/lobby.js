// Online lobby: challenges, quick match, join by code.
import { api } from '../core/api.js';
import { el, toast, toastError } from '../core/ui.js';
import { t } from '../core/i18n.js';
import { icon } from '../core/icons.js';

const list = document.getElementById('challenge-list');
const quickBtn = document.getElementById('btn-quick');
const tcSelect = document.getElementById('lobby-tc');
const ratedCheck = document.getElementById('lobby-rated');
const createForm = document.getElementById('create-form');
const codeInput = document.getElementById('join-code');
const queueBanner = document.getElementById('queue-banner');
const createTc = document.getElementById('create-tc');
const createRated = document.getElementById('create-rated');

let waiting = false;
let myChallengeCode = null;

const socket = io();

socket.on('connect', () => {
  socket.emit('lobby:state');
});

socket.on('lobby:state', (data) => {
  renderChallenges(data.challenges || []);
});

socket.on('queue:waiting', () => {
  waiting = true;
  queueBanner?.classList.remove('hidden');
  quickBtn.disabled = true;
});

socket.on('queue:cancelled', () => {
  waiting = false;
  queueBanner?.classList.add('hidden');
  quickBtn.disabled = false;
});

socket.on('challenge:created', (data) => {
  myChallengeCode = data.code;
  toast(t('lobby.challenge_created', { code: data.code }), 'success');
});

socket.on('challenge:cancelled', () => {
  myChallengeCode = null;
});

socket.on('game:started', (payload) => {
  window.location.href = `/game/${payload.game_id}`;
});

socket.on('error:toast', (data) => toastError(data.key));

function renderChallenges(challenges) {
  if (!list) return;
  list.innerHTML = '';
  if (!challenges.length) {
    list.append(el('div.empty-state', {},
      (() => { const s = el('span'); s.innerHTML = icon('swords'); return s; })(),
      el('div', {}, t('lobby.no_challenges'))));
    return;
  }
  for (const challenge of challenges) {
    const rated = challenge.rated ? t('lobby.rated') : t('lobby.casual');
    const mine = myChallengeCode === challenge.code;
    const row = el('div.challenge-row', {},
      el('span.avatar', {}, challenge.username[0]),
      el('div', {},
        el('div', { style: 'font-weight:600' }, challenge.username),
        el('div', { style: 'font-size:.78rem;color:var(--text-muted)' },
          `${challenge.rating} · ${challenge.tc} · ${rated}`),
      ),
      el('span.spacer'),
      mine ? el('span.badge.badge-accent', {}, t('lobby.your_challenge')) : null,
      mine ? el('button.btn.btn-ghost', {
        onclick: () => socket.emit('challenge:cancel'),
      }, t('common.cancel'))
        : el('button.btn.btn-primary', {
          onclick: () => socket.emit('challenge:join', { code: challenge.code }),
        }, icon('play'), t('lobby.join_btn')),
    );
    list.append(row);
  }
}

quickBtn?.addEventListener('click', () => {
  socket.emit('quick:join', {
    tc: tcSelect?.value || '5+0',
    rated: ratedCheck?.checked ?? true,
  });
});

document.getElementById('btn-cancel-queue')?.addEventListener('click', () => {
  socket.emit('quick:cancel');
});

createForm?.addEventListener('submit', (e) => {
  e.preventDefault();
  socket.emit('challenge:create', {
    tc: createTc?.value || '5+0',
    rated: createRated?.checked ?? false,
  });
});

document.getElementById('join-form')?.addEventListener('submit', (e) => {
  e.preventDefault();
  const code = (codeInput?.value || '').trim().toUpperCase();
  if (!code) return;
  socket.emit('challenge:join', { code });
});
