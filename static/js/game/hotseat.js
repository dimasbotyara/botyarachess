// Hotseat mode: two players on one screen, every move validated by the server.
import { api } from '../core/api.js';
import { toastError } from '../core/ui.js';
import { GameController } from './controller.js';

async function main() {
  const root = document.getElementById('game-root');
  const state = JSON.parse(root.dataset.state);
  const myColor = null; // both sides belong to the logged-in user

  const controller = new GameController({
    mode: 'hotseat',
    state,
    myColor,
    isPlayer: true,
    transport: {
      async sendMove(uci) {
        return api(`/api/games/${state.id}/move`, { method: 'POST', body: { uci } });
      },
      async resign() {
        try {
          const payload = await api(`/api/games/${state.id}/resign`, { method: 'POST' });
          controller.applyState(payload);
        } catch (error) { toastError(error); }
      },
      async undo() {
        try {
          const payload = await api(`/api/games/${state.id}/undo`, { method: 'POST' });
          controller.applyState(payload);
        } catch (error) { toastError(error); }
      },
      async newHotseat() {
        try {
          const { game_id } = await api('/api/games/hotseat', { method: 'POST' });
          return game_id;
        } catch (error) { toastError(error); return null; }
      },
    },
    boardEl: document.getElementById('board'),
  });

  // hotseat-only controls
  document.getElementById('btn-draw')?.classList.add('hidden');
  document.getElementById('btn-rematch')?.classList.add('hidden');
}

main();
