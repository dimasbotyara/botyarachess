// AI mode: the LLM opponent, its chat bubble and the manual paste-mode flow.
import { api } from '../core/api.js';
import { toast, toastError } from '../core/ui.js';
import { GameController } from './controller.js';

async function main() {
  const root = document.getElementById('game-root');
  const state = JSON.parse(root.dataset.state);
  const myColor = root.dataset.myColor;
  const isManual = root.dataset.aiProvider === 'manual';

  let thinking = false;

  const controller = new GameController({
    mode: 'ai',
    state,
    myColor,
    isPlayer: true,
    transport: {
      ai: state.ai || { chat_enabled: true },
      async sendMove(uci) {
        thinking = true;
        controller.setThinking(true);
        try {
          const message = (document.getElementById('chat-input')?.value || '').trim();
          const payload = await api(`/api/games/${state.id}/move`, {
            method: 'POST',
            body: { uci, message },
          });
          if (document.getElementById('chat-input')) {
            document.getElementById('chat-input').value = '';
          }
          return payload;
        } finally {
          thinking = false;
          controller.setThinking(false);
        }
      },
      async loadManualPrompt({ isRetry = false } = {}) {
        try {
          const { prompt } = await api(`/api/games/${state.id}/manual_prompt`);
          controller.showManualPrompt(prompt, { isRetry });
        } catch (error) { toastError(error); }
      },
      async manualReply(text) {
        try {
          const payload = await api(`/api/games/${state.id}/manual_reply`, {
            method: 'POST',
            body: { text },
          });
          controller.applyState(payload, { flags: payload.flags || {} });
          return true;
        } catch (error) {
          if (error.status === 400 && error.data?.retry_prompt) {
            controller.showManualPrompt(error.data.retry_prompt, { isRetry: true });
          } else {
            toastError(error);
          }
          return false;
        }
      },
      async undo() {
        if (thinking) return;
        try {
          const payload = await api(`/api/games/${state.id}/undo`, { method: 'POST' });
          controller.applyState(payload);
        } catch (error) { toastError(error); }
      },
      async resign() {
        try {
          const payload = await api(`/api/games/${state.id}/resign`, { method: 'POST' });
          controller.applyState(payload);
        } catch (error) { toastError(error); }
      },
      chat(text) {
        // goes to the model together with the next move; show immediately
        controller.showPlayerBubble(text);
      },
    },
    boardEl: document.getElementById('board'),
  });

  // AI chat is sent together with the next move; chat UI stays visible
  if (isManual) {
    document.getElementById('ai-chat')?.classList.add('hidden');
    controller.showManualSection?.();
    document.getElementById('manual-box')?.classList.remove('hidden');
    // If it is already the AI's turn on load (fresh game with AI as white),
    // fetch the first prompt.
    if (state.status === 'active' && state.turn !== myColor) {
      await controller.transport.loadManualPrompt();
    }
  } else {
    document.getElementById('manual-box')?.classList.add('hidden');
    // AI plays white on a fresh game: nudge it once.
    if (state.status === 'active' && state.turn !== myColor
        && state.moves.length === 0) {
      try {
        const payload = await api(`/api/games/${state.id}/move`, {
          method: 'POST', body: { uci: '' },
        });
        controller.applyState(payload, { flags: payload.flags || {} });
      } catch (error) { toastError(error); }
    }
  }

  document.getElementById('btn-draw')?.classList.add('hidden');
  document.getElementById('btn-rematch')?.classList.add('hidden');
}

main();
