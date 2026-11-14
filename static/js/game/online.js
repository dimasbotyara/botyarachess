// Online mode: SocketIO transport (moves, chat, clocks, draw, rematch).
/* global io */
import { toast, toastError } from '../core/ui.js';
import { t } from '../core/i18n.js';
import { sounds } from '../core/sounds.js';
import { GameController } from './controller.js';

async function main() {
  const root = document.getElementById('game-root');
  const state = JSON.parse(root.dataset.state);
  const myColor = root.dataset.myColor || null;
  const isPlayer = root.dataset.isPlayer === '1';
  const gameId = state.id;

  let controller;
  const socket = io({ transports: ['websocket', 'polling'] });

  socket.on('connect', () => {
    socket.emit('game:join', { game_id: gameId });
  });

  socket.on('game:state', (payload) => {
    controller.applyState(payload);
  });

  socket.on('game:move', (payload) => {
    controller.applyState(payload, { flags: payload.flags || {} });
  });

  socket.on('game:over', (payload) => {
    controller.stopClocks();
    if (payload.state) {
      controller.applyState(payload.state, { flags: { game_over: true } });
    }
  });

  socket.on('game:chat', (data) => {
    if (data.user_id === myUserId()) return; // already shown optimistically
    controller.appendChatMessage({ sender: 'other',
      username: data.username, text: data.text, kind: 'text' });
  });

  socket.on('game:draw:offered', (data) => {
    sounds.notify();
    const accept = window.confirm(t('game.draw_incoming', { name: data.username }));
    if (accept) socket.emit('game:draw:accept', { game_id: gameId });
    else socket.emit('game:draw:decline', { game_id: gameId });
  });

  socket.on('game:draw:declined', () => {
    toast(t('game.draw_declined'), 'info');
  });

  socket.on('game:rematch:offered', (data) => {
    sounds.notify();
    if (window.confirm(t('game.rematch_incoming', { name: data.username }))) {
      socket.emit('game:rematch', { game_id: gameId });
    }
  });

  socket.on('player:disconnected', (data) => {
    if (data.color !== myColor) {
      toast(t('game.opponent_left', { sec: data.grace }), 'error', 6000);
    }
  });

  socket.on('player:reconnected', () => {
    toast(t('game.opponent_back'), 'success');
  });

  socket.on('game:started', (payload) => {
    window.location.href = `/game/${payload.game_id}`;
  });

  socket.on('error:toast', (data) => toastError(data.key));

  function myUserId() {
    return Number(root.dataset.userId || 0);
  }

  controller = new GameController({
    mode: 'online',
    state,
    myColor,
    isPlayer,
    transport: {
      sendMove(uci) {
        socket.emit('game:move', { game_id: gameId, uci });
        return new Promise((resolve) => { resolve({ ok: true }); });
      },
      resign() { socket.emit('game:resign', { game_id: gameId }); },
      offerDraw() { socket.emit('game:draw:offer', { game_id: gameId }); },
      rematch() { socket.emit('game:rematch', { game_id: gameId }); },
      chat(text) {
        socket.emit('game:chat', { game_id: gameId, text });
        controller.appendChatMessage({ sender: 'player', username: root.dataset.username, text, kind: 'text' });
      },
    },
    boardEl: document.getElementById('board'),
  });

  document.getElementById('btn-undo')?.classList.add('hidden');
  document.getElementById('btn-autoflip')?.classList.add('hidden');
  if (!isPlayer) {
    document.getElementById('btn-resign')?.classList.add('hidden');
    document.getElementById('btn-draw')?.classList.add('hidden');
  }
}

main();
