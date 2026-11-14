// Shared game-page orchestrator used by all three modes (hotseat / AI / online).
//
// Owns the board, chess.js mirror of the position, move list, clocks,
// captured pieces, status line, chat and the end-of-game modal. Mode scripts
// (hotseat.js / ai.js / online.js) provide a `transport` that knows how to
// send moves and receive server state.

import { Chess } from '../../vendor/chess.js';
import { ChessBoardUI } from '../board/board.js';
import { pieceUrl, preloadPieces } from '../board/pieces.js';
import { el, esc, toast, toastError, formatClock, openModal, confirmModal, copyText } from '../core/ui.js';
import { t, getLang } from '../core/i18n.js';
import { sounds, unlockAudio } from '../core/sounds.js';
import { icon } from '../core/icons.js';

preloadPieces();

const PIECE_VALUES = { p: 1, n: 3, b: 3, r: 5, q: 9, k: 0 };
const START_COUNTS = { p: 8, n: 2, b: 2, r: 2, q: 1, k: 1 };

export class GameController {
  constructor({ mode, state, myColor, isPlayer, transport, boardEl }) {
    this.mode = mode;
    this.state = state;
    this.myColor = myColor;          // 'white' | 'black' | null (hotseat both)
    this.isPlayer = isPlayer;
    this.transport = transport;
    this.chess = new Chess();
    this.chess.load(state.fen);
    this.viewPly = state.moves.length;  // which position is displayed
    // device override wins, then the profile setting
    const storedFlip = localStorage.getItem('botyarachess.autoflip');
    let profileSettings = {};
    try { profileSettings = JSON.parse(document.body.dataset.settings || '{}'); } catch { /* */ }
    this.autoFlip = storedFlip !== null
      ? storedFlip === '1'
      : (profileSettings.autoflip ?? false);
    this.overHandled = false;

    this._clockTimer = null;
    this._clockBase = null;

    unlockAudio();
    this._buildBoard(boardEl);
    this._collectDom();
    this._wireControls();
    this.applyState(state, { silent: true });
    this._renderChat(state.chat || []);
    if (mode === 'ai' && (transport.ai || {}).chat_enabled === false) {
      document.getElementById('ai-chat')?.classList.add('hidden');
      document.getElementById('ai-chat')?.remove();
    }
  }

  // ------------------------------------------------------------- structure
  _buildBoard(boardEl) {
    const movableColor = this.mode === 'hotseat' ? (this.myColor || null) : this.myColor;
    this.board = new ChessBoardUI(boardEl, {
      orientation: this.myColor === 'black' ? 'black' : 'white',
      coords: true,
      movableColor: this.isPlayer ? movableColor : 'nobody',
      getMoves: (square) => this._legalTargets(square),
      onAttemptMove: ({ from, to, promotion }) => this._attemptMove(from, to, promotion),
    });
  }

  _legalTargets(square) {
    if (this.state.status !== 'active') return [];
    if (this.mode === 'online' && this.state.turn !== this.myColor) return [];
    if (this.mode === 'ai' && this.state.turn !== this.myColor) return [];
    if (this.mode === 'hotseat' && this.myColor
        && this.state.turn !== this.myColor) return [];
    if (this.viewPly !== this.state.moves.length) return [];
    return this.chess.moves({ square, verbose: true }).map((m) => m.to);
  }

  _collectDom() {
    const $ = (id) => document.getElementById(id);
    this.dom = {
      topBar: $('player-top'), bottomBar: $('player-bottom'),
      board: $('board'),
      moveList: $('moves-list'),
      status: $('status-line'),
      thinking: $('thinking-banner'),
      controls: $('controls'),
      chatLog: $('chat-log'),
      chatSection: $('chat-section'),
      chatInput: $('chat-input'),
      chatSend: $('chat-send'),
      aiBubble: $('ai-bubble'),
      aiBubbleText: $('ai-bubble-text'),
      aiChat: $('ai-chat'),
      manualBox: $('manual-box'),
      manualPrompt: $('manual-prompt'),
      manualReply: $('manual-reply'),
      capturedTop: $('captured-top'),
      capturedBottom: $('captured-bottom'),
      clockTop: $('clock-top'),
      clockBottom: $('clock-bottom'),
    };
  }

  _wireControls() {
    const $ = (id) => document.getElementById(id);
    $('btn-flip')?.addEventListener('click', () => {
      this.board.flip();
    });
    $('btn-sound')?.addEventListener('click', (e) => {
      const muted = localStorage.getItem('botyarachess.muted') === '1';
      localStorage.setItem('botyarachess.muted', muted ? '0' : '1');
      this._updateSoundButton();
      if (!muted) toast(t('game.unmute'), 'info', 1500);
      e.currentTarget.blur();
    });
    this._updateSoundButton();

    $('btn-resign')?.addEventListener('click', async () => {
      if (!await confirmModal({ titleKey: 'game.resign_confirm', icon: 'flag', danger: true })) return;
      this.transport.resign?.();
    });
    $('btn-undo')?.addEventListener('click', () => this.transport.undo?.());
    $('btn-draw')?.addEventListener('click', () => this.transport.offerDraw?.());
    $('btn-rematch')?.addEventListener('click', () => this.transport.rematch?.());
    $('btn-pgn')?.addEventListener('click', () => {
      window.open(`/api/games/${this.state.id}/pgn`, '_blank');
    });
    $('btn-autoflip')?.addEventListener('click', (e) => {
      this.autoFlip = !this.autoFlip;
      localStorage.setItem('botyarachess.autoflip', this.autoFlip ? '1' : '0');
      e.currentTarget.classList.toggle('btn-primary', this.autoFlip);
    });
    const autoBtn = $('btn-autoflip');
    if (autoBtn && this.autoFlip) autoBtn.classList.add('btn-primary');

    // chat
    const sendChat = () => {
      const text = (this.dom.chatInput?.value || '').trim();
      if (!text) return;
      this.dom.chatInput.value = '';
      this.transport.chat?.(text);
    };
    this.dom.chatSend?.addEventListener('click', sendChat);
    this.dom.chatInput?.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendChat(); }
    });

    // move navigation (shown once the game is finished)
    document.getElementById('nav-start')?.addEventListener('click', () => this._jumpTo(0));
    document.getElementById('nav-prev')?.addEventListener('click', () => this._jumpTo(this.viewPly - 1));
    document.getElementById('nav-next')?.addEventListener('click', () => this._jumpTo(this.viewPly + 1));
    document.getElementById('nav-end')?.addEventListener('click', () => this._jumpTo(this.state.moves.length));
    document.addEventListener('keydown', (e) => {
      if (!this.overHandled) return;              // only in finished games
      if (e.target.matches('input, textarea')) return;
      if (e.key === 'ArrowLeft') this._jumpTo(this.viewPly - 1);
      if (e.key === 'ArrowRight') this._jumpTo(this.viewPly + 1);
    });

    // manual mode
    $('manual-copy')?.addEventListener('click', () => {
      copyText(this.dom.manualPrompt.value);
    });
    $('manual-submit')?.addEventListener('click', () => {
      const text = (this.dom.manualReply?.value || '').trim();
      if (!text) return;
      this.transport.manualReply?.(text);
    });
  }

  _updateSoundButton() {
    const btn = document.getElementById('btn-sound');
    if (!btn) return;
    const muted = localStorage.getItem('botyarachess.muted') === '1';
    btn.dataset.icon = muted ? 'volume-x' : 'volume-2';
    btn.innerHTML = icon(muted ? 'volume-x' : 'volume-2');
    btn.title = t(muted ? 'game.unmute' : 'game.mute');
  }

  // ---------------------------------------------------------- state updates
  /** The one entry point every transport uses to sync UI with the server. */
  applyState(state, { flags = {}, silent = false } = {}) {
    const finishedNow = this.state.status === 'active' && state.status === 'finished';
    this.state = state;
    this.chess.load(state.fen);
    this.viewPly = state.moves.length;

    this._syncBoard(flags, silent);
    this._renderPlayers();
    this._renderMoves();
    this._renderCaptured();
    this._renderStatus();
    if (state.clocks) this.setClocks(state.clocks);

    if (flags.game_over || finishedNow || state.status === 'finished') {
      this.board.setViewOnly(true);
      document.getElementById('game-nav')?.classList.add('visible');
      // the result modal is only for games that just ended on screen
      if ((flags.game_over || finishedNow) && !this.overHandled) {
        this.overHandled = true;
        if (!silent) sounds.gameEnd();
        this._showResultModal(state);
      }
    }
    // enable end-game affordances
    document.getElementById('btn-pgn')?.classList.toggle('hidden', state.moves.length === 0);
  }

  _syncBoard(flags, silent) {
    const moveCount = this.state.moves.length;
    const last = this.state.last_move
      ? { from: this.state.last_move.slice(0, 2), to: this.state.last_move.slice(2, 4) }
      : null;

    // highlight the square of a king in check
    let checkSquare = null;
    if (this.state.check) {
      const board = this.chess.board();
      for (let r = 0; r < 8; r += 1) {
        for (let f = 0; f < 8; f += 1) {
          const piece = board[r][f];
          if (piece && piece.type === 'k' && piece.color === (this.state.turn === 'white' ? 'w' : 'b')) {
            checkSquare = 'abcdefgh'[f] + (8 - r);
          }
        }
      }
    }

    this.board.setPosition(this.state.fen);
    this.board.setHighlights({
      lastMove: last,
      checkSquare,
      selected: null,
      legalTargets: [],
    });

    if (this.mode === 'hotseat' && this.autoFlip && !this.overHandled) {
      this.board.setOrientation(this.state.turn);
    }

    if (!silent && moveCount > 0 && !this.overHandled) {
      if (flags.game_over || this.state.status === 'finished') {
        // handled in applyState
      } else if (flags.check) {
        sounds.check();
      } else if (flags.castle) {
        sounds.castle();
      } else if (flags.capture) {
        sounds.capture();
      } else {
        sounds.move();
      }
    }
    this.board.setViewOnly(!this.isPlayer || this.state.status !== 'active'
      || this._cannotMoveNow());
  }

  _cannotMoveNow() {
    if (this.mode === 'hotseat') return false;
    return this.state.turn !== this.myColor;
  }

  // ------------------------------------------------------------- rendering
  _renderPlayers() {
    const { players } = this.state;
    const white = players.white.username || t('game.ai_name');
    const black = players.black.username || t('game.ai_name');
    const bottomColor = this.board.orientation;
    const topColor = bottomColor === 'white' ? 'black' : 'white';
    const names = {
      white: { name: white, rating: players.white.rating },
      black: { name: black, rating: players.black.rating },
    };
    this._fillPlayerBar(this.dom.bottomBar, bottomColor, names[bottomColor]);
    this._fillPlayerBar(this.dom.topBar, topColor, names[topColor]);
  }

  _fillPlayerBar(bar, color, { name, rating }) {
    if (!bar) return;
    const isMe = this.myColor === color && this.isPlayer;
    const label = isMe ? `${name} · ${t('common.you')}` : name;
    const initial = esc((name || '?')[0]);
    bar.innerHTML = `
      <span class="avatar">${initial}</span>
      <div>
        <div class="p-name">${label}</div>
        <div class="p-sub">${t('common.' + color)}${rating != null ? ' · ' + rating : ''}</div>
      </div>
      <div class="spacer"></div>
      <div class="captured" id="cap-${color}"></div>
      ${this.state.clocks ? `<div class="clock" id="clock-${color}">--:--</div>` : ''}`;
    this._renderCaptured();
    if (this.state.clocks) {
      this.dom.clockTop = document.getElementById('clock-top');
      this.dom.clockBottom = document.getElementById('clock-bottom');
    }
  }

  _renderMoves() {
    const list = this.dom.moveList;
    if (!list) return;
    const moves = this.state.moves;
    const rows = [];
    for (let i = 0; i < moves.length; i += 2) {
      const white = moves[i];
      const black = moves[i + 1];
      rows.push(el('li', {},
        el('span.move-num', {}, `${i / 2 + 1}.`),
        el('span.move', {
          dataset: { ply: i + 1 },
          onclick: () => this._jumpTo(i + 1),
        }, white.san),
        black ? el('span.move', {
          dataset: { ply: i + 2 },
          onclick: () => this._jumpTo(i + 2),
        }, black.san) : el('span.move', {}, ''),
      ));
    }
    const ol = el('ol', {}, rows);
    list.innerHTML = '';
    list.append(ol);
    list.scrollTop = list.scrollHeight;
    this._markCurrentPly();
  }

  _markCurrentPly() {
    this.dom.moveList?.querySelectorAll('.move').forEach((node) => {
      node.classList.toggle('current', Number(node.dataset.ply) === this.viewPly);
    });
  }

  /** Step through a finished (or running) game without touching the server. */
  _jumpTo(ply) {
    if (this.mode === 'online' && this.state.status === 'active') return;
    if (ply === this.state.moves.length) {
      this.viewPly = ply;
      this.chess.load(this.state.fen);
      this.board.setPosition(this.state.fen);
      this._markCurrentPly();
      this.board.setViewOnly(true);
      return;
    }
    const replay = new Chess();
    for (let i = 0; i < ply; i += 1) replay.move(this.state.moves[i].san);
    this.viewPly = ply;
    this.board.setPosition(replay.fen());
    this.board.setHighlights({});
    this.board.setViewOnly(true);
    this._markCurrentPly();
  }

  _renderCaptured() {
    const counts = { w: {}, b: {} };
    for (const key of Object.keys(START_COUNTS)) { counts.w[key] = 0; counts.b[key] = 0; }
    const board = this.chess.board();
    for (let r = 0; r < 8; r += 1) {
      for (let f = 0; f < 8; f += 1) {
        const piece = board[r]?.[f];
        if (piece) counts[piece.color][piece.type] += 1;
      }
    }
    // pieces captured BY white = missing black pieces (and vice versa)
    const capturedBy = { w: [], b: [] };
    for (const color of ['w', 'b']) {
      const enemy = color === 'w' ? 'b' : 'w';
      for (const [type, start] of Object.entries(START_COUNTS)) {
        const missing = Math.max(0, start - counts[enemy][type]);
        for (let i = 0; i < missing; i += 1) capturedBy[color].push(type);
      }
    }
    const material = (color) => capturedBy[color]
      .reduce((sum, type) => sum + PIECE_VALUES[type], 0);
    const diff = material('w') - material('b');

    const render = (container, victims, victimColor, advantage) => {
      if (!container) return;
      container.innerHTML = '';
      for (const type of victims) {
        const img = document.createElement('img');
        img.src = pieceUrl(type, victimColor);
        container.append(img);
      }
      if (advantage > 0) container.append(el('span.diff', {}, `+${advantage}`));
    };

    // bottom bar shows pieces captured by the player on the bottom side
    const bottomColor = this.board.orientation;
    const topColor = bottomColor === 'white' ? 'black' : 'white';
    const bottomVictims = bottomColor === 'white' ? capturedBy.w : capturedBy.b;
    const topVictims = bottomColor === 'white' ? capturedBy.b : capturedBy.w;
    const bottomAdv = bottomColor === 'white' ? Math.max(0, diff) : Math.max(0, -diff);
    const topAdv = bottomColor === 'white' ? Math.max(0, -diff) : Math.max(0, diff);

    render(document.getElementById(`cap-${bottomColor}`), bottomVictims,
      bottomColor === 'white' ? 'b' : 'w', bottomAdv);
    render(document.getElementById(`cap-${topColor}`), topVictims,
      topColor === 'white' ? 'b' : 'w', topAdv);
  }

  _renderStatus() {
    const node = this.dom.status;
    if (!node) return;
    node.classList.remove('alert', 'win');
    let text = '';
    let iconName = 'info';
    if (this.state.status === 'finished') {
      text = `${t('game.game_over')} · ${t('term.' + this.state.termination)}`;
      iconName = 'check';
      node.classList.add('win');
    } else if (this.mode === 'ai' && this.state.turn !== this.myColor) {
      text = t('game.thinking');
      iconName = 'brain';
      node.classList.add('alert');
    } else if (this.mode === 'hotseat') {
      text = t('game.hotseat_turn', {
        color: t('common.' + this.state.turn).toLowerCase(),
      });
      if (this.state.check) {
        text += ` · ${t('game.check')}`;
        node.classList.add('alert');
      }
      iconName = 'swords';
    } else {
      text = this.state.turn === this.myColor ? t('game.your_turn') : t('game.waiting');
      if (this.state.check && this.state.turn === this.myColor) {
        text += ` · ${t('game.check')}`;
        node.classList.add('alert');
      }
      iconName = 'zap';
    }
    node.innerHTML = `${icon(iconName)}<span>${esc(text)}</span>`;
    this.dom.thinking?.classList.toggle('visible',
      this.mode === 'ai' && this.state.status === 'active' && this.state.turn !== this.myColor);
  }

  // ------------------------------------------------------------------ chat
  _renderChat(messages) {
    if (!this.dom.chatLog) return;
    this.dom.chatLog.innerHTML = '';
    for (const msg of messages) this._appendChat(msg, { scroll: false });
    this._scrollChat();
  }

  _appendChat(msg, { scroll = true } = {}) {
    if (!this.dom.chatLog) return;
    let text;
    if (msg.kind === 'key') {
      if (msg.text.startsWith('ai.provider_error|')) {
        text = t('ai.provider_error|{msg}', { msg: msg.text.slice(18) }).replace('{msg}', msg.text.slice(18));
      } else {
        text = t(msg.text);
      }
    } else {
      text = msg.text;
    }
    const isMe = msg.sender === 'player';
    const who = isMe
      ? (this.state.players[this.myColor || 'white']?.username || t('common.you'))
      : (this.mode === 'ai' ? t('game.ai_name') : msg.username || '?');
    const row = el(`div.chat-msg${isMe ? ' me' : ''}`, {},
      el('span.who', {}, who + ':'),
      el('span.txt', {}, text),
    );
    this.dom.chatLog.append(row);
    if (scroll) this._scrollChat();
    if (this.mode === 'ai' && !isMe && msg.sender === 'ai') {
      this._showAiBubble(text);
      if (!this.overHandled) sounds.notify();
    }
  }

  _showAiBubble(text) {
    if (!this.dom.aiBubbleText) return;
    this.dom.aiBubbleText.textContent = text;
    this.dom.aiBubble?.classList.remove('hidden');
    this.dom.aiChat?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  /** Player message shown instantly while waiting for the AI reply. */
  showPlayerBubble(text) {
    if (this.mode !== 'ai' || !this.dom.aiBubbleText) return;
    this.dom.aiBubbleText.textContent = text;
    this.dom.aiBubble?.classList.remove('hidden');
  }

  setThinking(flag) {
    this.dom.thinking?.classList.toggle('visible', flag);
  }

  _scrollChat() {
    const log = this.dom.chatLog;
    if (log) log.scrollTop = log.scrollHeight;
  }

  appendChatMessage(msg) {
    this._appendChat(msg);
  }

  // ---------------------------------------------------------------- manual
  showManualPrompt(prompt, { isRetry = false } = {}) {
    if (!this.dom.manualBox) return;
    this.dom.manualBox.classList.remove('hidden');
    this.dom.manualPrompt.value = prompt;
    if (isRetry) {
      toast(t('ai.manual_retry'), 'error', 6000);
    } else {
      toast(t('ai.manual_prompt_ready'), 'info', 4500);
    }
  }

  // ---------------------------------------------------------------- clocks
  setClocks(payload) {
    if (!payload) return;
    this._clockBase = payload;
    if (this._clockTimer) clearInterval(this._clockTimer);
    this._clockTimer = setInterval(() => this._tickClocks(), 200);
    this._tickClocks();
  }

  _tickClocks() {
    const base = this._clockBase;
    if (!base) return;
    const elapsed = (Date.now() / 1000 - base.server_ts) * 1000;
    const values = { white: base.white, black: base.black };
    if (base.running) {
      values[base.running] = Math.max(0, values[base.running] - elapsed);
    }
    for (const color of ['white', 'black']) {
      const clockNode = color === this.board.orientation
        ? this.dom.clockBottom : this.dom.clockTop;
      if (!clockNode) continue;
      clockNode.textContent = formatClock(values[color]);
      clockNode.classList.toggle('running', base.running === color
        && this.state.status === 'active');
      clockNode.classList.toggle('low', values[color] < 30000);
    }
  }

  stopClocks() {
    if (this._clockTimer) clearInterval(this._clockTimer);
    this._clockTimer = null;
  }

  // ------------------------------------------------------------------ move
  async _attemptMove(from, to, promotion) {
    const move = this.chess.move({ from, to, promotion: promotion || undefined });
    if (!move) {
      sounds.illegal();
      return false;
    }
    this.chess.undo(); // the authoritative state comes from the server
    try {
      const payload = await this.transport.sendMove(move.from + move.to + (move.promotion || ''));
      // online transport returns null: the authoritative state arrives via socket
      if (!payload) return true;
      if (payload.error) {
        sounds.illegal();
        toastError(payload.error);
        return false;
      }
      this.applyState(payload, { flags: payload.flags || {} });
      if (payload.need_prompt) {
        await this.transport.loadManualPrompt?.();
      }
      return true;
    } catch (error) {
      sounds.illegal();
      toastError(error);
      return false;
    }
  }

  // ---------------------------------------------------------- game over UI
  _showResultModal(state) {
    const isDraw = state.result === '1/2-1/2';
    const winner = state.result === '1-0' ? 'white'
      : (state.result === '0-1' ? 'black' : null);
    let title;
    let iconName;
    if (isDraw) {
      title = t('game.drawn');
      iconName = 'handshake';
    } else if (this.mode === 'hotseat') {
      title = `${t('common.' + winner)} — ${t('game.victory')}`;
      iconName = 'trophy';
    } else {
      const iWon = winner === this.myColor;
      title = iWon ? t('game.victory') : t('game.defeat');
      iconName = iWon ? 'trophy' : 'x';
    }

    const content = el('div', { style: 'text-align:center' });
    const iconHolder = el('span');
    iconHolder.innerHTML = icon(iconName, 'result-icon');
    content.append(
      iconHolder,
      el('h3', {}, title),
      el('p', { style: 'color:var(--text-muted)' }, t('term.' + state.termination)),
    );

    const actions = el('div.modal-actions', { style: 'justify-content:center; flex-wrap:wrap' });
    if (this.mode === 'online') {
      actions.append(el('button.btn.btn-primary', { onclick: () => { this.transport.rematch?.(); modal.close(); } },
        icon('refresh-cw'), t('game.rematch')));
    } else if (this.mode === 'ai') {
      actions.append(el('a.btn.btn-primary', { href: '/play/ai' }, icon('refresh-cw'), t('game.new_game')));
    } else {
      actions.append(el('button.btn.btn-primary', { onclick: async () => {
        const created = await this.transport.newHotseat?.();
        if (created) window.location.href = `/game/${created}`;
      } }, icon('refresh-cw'), t('game.new_game')));
    }
    actions.append(el('a.btn', { href: '/games' }, icon('history'), t('nav.history')));
    content.append(actions);
    const modal = openModal(content, { dismissible: true });
  }
}
