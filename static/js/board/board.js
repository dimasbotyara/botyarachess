// Vanilla-JS chessboard renderer.
//
// - grid of 64 squares, pieces are absolutely positioned inside squares
// - pointer-events drag & drop (mouse + touch), plus click-click moves
// - highlights: last move, selection, legal targets (dots/rings), check
// - promotion picker overlay, board flip, coordinates
//
// The board never validates chess rules itself; it asks `opts.getMoves(square)`
// for legal targets and reports `onAttemptMove({from, to, promotion})` — the
// caller decides whether the move happened (server-side python-chess rules).

const FILES = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h'];
const RANKS = ['1', '2', '3', '4', '5', '6', '7', '8'];

const PROMO_CHOICES = ['q', 'r', 'b', 'n'];
import { pieceUrl } from './pieces.js';

export class ChessBoardUI {
  constructor(wrap, opts = {}) {
    this.wrap = wrap;
    this.opts = opts;
    this.orientation = opts.orientation || 'white';
    this.coords = opts.coords ?? true;
    this.animation = opts.animation ?? true;
    this.highlights = opts.highlightLegal ?? true;

    this.pieces = new Map();     // square -> {type, color, el}
    this.selected = null;
    this.drag = null;
    this.lastMove = null;
    this.checkSquare = null;
    this.viewOnly = false;
    this.autoFlip = false;

    this.el = document.createElement('div');
    this.el.className = 'chessboard';
    wrap.append(this.el);
    wrap.classList.add('board-wrap');

    this.squares = new Map();    // square -> element
    this._buildSquares();
    this._bindPointer();

    this._promoResolve = null;
    this.promoOverlay = null;
  }

  // ------------------------------------------------------------- structure
  _squareOrder() {
    // returns square names in render order for the current orientation
    const ranks = this.orientation === 'white' ? [...RANKS].reverse() : [...RANKS];
    const files = this.orientation === 'white' ? [...FILES] : [...FILES].reverse();
    const order = [];
    for (const rank of ranks) for (const file of files) order.push(file + rank);
    return order;
  }

  _buildSquares() {
    this.el.innerHTML = '';
    this.squares.clear();
    for (const square of this._squareOrder()) {
      const file = FILES.indexOf(square[0]);
      const rank = Number(square[1]);
      const light = (file + rank) % 2 === 1;
      const cell = document.createElement('div');
      cell.className = `square ${light ? 'light' : 'dark'}`;
      cell.dataset.square = square;
      if (this.coords) {
        const isLeftCol = (this.orientation === 'white' ? file === 0 : file === 7);
        const isBottomRow = (this.orientation === 'white' ? rank === 1 : rank === 8);
        if (isLeftCol) {
          const c = document.createElement('span');
          c.className = 'coord rank';
          c.textContent = rank;
          cell.append(c);
        }
        if (isBottomRow) {
          const c = document.createElement('span');
          c.className = 'coord file';
          c.textContent = file >= 0 ? square[0] : '';
          cell.append(c);
        }
      }
      this.el.append(cell);
      this.squares.set(square, cell);
    }
    // re-place existing pieces into the new layout
    for (const [square, piece] of this.pieces) {
      const cell = this.squares.get(square);
      if (cell) cell.append(piece.el);
    }
  }

  // ---------------------------------------------------------------- pieces
  _makePieceEl(type, color) {
    const holder = document.createElement('div');
    holder.className = 'piece';
    const img = document.createElement('img');
    img.src = pieceUrl(type, color);
    img.draggable = false;
    img.alt = '';
    holder.append(img);
    return holder;
  }

  _parseFenBoard(fen) {
    const placement = fen.split(' ')[0];
    const map = new Map();
    let rank = 8;
    let file = 0;
    for (const ch of placement) {
      if (ch === '/') { rank -= 1; file = 0; continue; }
      if (/\d/.test(ch)) { file += Number(ch); continue; }
      const color = ch === ch.toUpperCase() ? 'w' : 'b';
      map.set(FILES[file] + rank, { type: ch.toLowerCase(), color });
      file += 1;
    }
    return map;
  }

  setPosition(fen, { animate = true } = {}) {
    const target = this._parseFenBoard(fen);

    // Pass 1: keep identical pieces in place; collect the rest.
    const removed = [];
    for (const [square, piece] of this.pieces) {
      const next = target.get(square);
      if (next && next.type === piece.type && next.color === piece.color) {
        target.delete(square);            // stays put
      } else {
        removed.push({ square, piece });
      }
    }
    const added = [...target.entries()];  // squares that need a fresh piece

    // Pass 2: pair up added pieces with removed pieces of the same type and
    // colour — that turns captures (pawn vanishes, queen appears on its
    // square) and castling (two movers) into slide animations instead of a
    // full re-render.
    const pairs = [];
    const consumed = new Set();
    for (const [toSquare, info] of added) {
      const matchIdx = removed.findIndex((r, i) => !consumed.has(i)
        && r.piece.type === info.type && r.piece.color === info.color);
      if (matchIdx >= 0) {
        consumed.add(matchIdx);
        pairs.push({ from: removed[matchIdx], toSquare, info });
      }
    }
    const vanished = removed.filter((_, i) => !consumed.has(i));

    // viewOnly blocks *input*, not animations — review / finished games
    // still want sliding pieces.
    const doAnimate = animate && this.animation && pairs.length > 0;

    if (!doAnimate) {
      for (const { square, piece } of removed) {
        piece.el.remove();
        if (this.pieces.get(square) === piece) this.pieces.delete(square);
      }
      for (const [square, info] of added) {
        const pieceEl = this._makePieceEl(info.type, info.color);
        this.pieces.set(square, { ...info, el: pieceEl });
        this.squares.get(square)?.append(pieceEl);
      }
      return;
    }

    // Animated path: matched pieces slide, captured pieces vanish with a
    // fade, re-appearing pieces (stepping backwards over a capture) pop in.
    for (const { square, piece } of vanished) {
      if (this.pieces.get(square) === piece) this.pieces.delete(square);
      piece.el.classList.add('vanishing');
      setTimeout(() => piece.el.remove(), 200);
    }
    for (const [square, info] of added) {
      if (pairs.some((p) => p.toSquare === square)) continue; // handled below
      const pieceEl = this._makePieceEl(info.type, info.color);
      pieceEl.classList.add('spawning');
      this.pieces.set(square, { ...info, el: pieceEl });
      this.squares.get(square)?.append(pieceEl);
      setTimeout(() => pieceEl.classList.remove('spawning'), 220);
    }
    for (const pair of pairs) {
      const movingEl = pair.from.piece.el;
      const fromRect = movingEl.getBoundingClientRect();
      this.pieces.delete(pair.from.square);
      this.pieces.set(pair.toSquare, { ...pair.info, el: movingEl });
      const toCell = this.squares.get(pair.toSquare);
      if (!toCell) continue;
      toCell.append(movingEl);
      const toRect = toCell.getBoundingClientRect();
      const dx = fromRect.left - toRect.left;
      const dy = fromRect.top - toRect.top;
      if (dx || dy) {
        // FLIP without requestAnimationFrame (rAF never fires in throttled or
        // hidden tabs, which turned every animation into an instant jump).
        // Order matters: commit the offset WITHOUT any transition, then
        // enable the transition and clear the transform so the browser
        // interpolates from the committed start value to the rest position.
        movingEl.style.transform = `translate(${dx}px, ${dy}px)`;
        void movingEl.offsetWidth;           // commit the start value
        movingEl.classList.add('animating'); // transition: transform .16s
        movingEl.style.transform = '';       // animate back to rest
        setTimeout(() => {
          movingEl.classList.remove('animating');
          movingEl.style.transform = '';
        }, 240);
      }
    }
  }

  // ------------------------------------------------------------ highlights
  setHighlights({ lastMove = null, checkSquare = null, selected = null,
                  legalTargets = [] } = {}) {
    this.lastMove = lastMove;
    this.checkSquare = checkSquare;
    this.selected = selected;
    this._legalTargets = legalTargets;
    this._refreshHighlightClasses();
  }

  _refreshHighlightClasses() {
    const targets = new Set(this._legalTargets || []);
    for (const [square, cell] of this.squares) {
      cell.classList.toggle('hl-last',
        !!this.lastMove && (square === this.lastMove.from || square === this.lastMove.to));
      cell.classList.toggle('hl-select', square === this.selected);
      cell.classList.toggle('hl-check', square === this.checkSquare);
      const legal = this.highlights && targets.has(square);
      cell.classList.toggle('hl-legal', legal);
      cell.classList.toggle('has-piece', legal && this.pieces.has(square));
    }
  }

  setCoords(show) {
    this.coords = show;
    this._buildSquares();
    // rebuild loses pieces; re-place them
    for (const [square, piece] of this.pieces) {
      this.squares.get(square)?.append(piece.el);
    }
    this._refreshHighlightClasses();
  }

  setOrientation(orientation) {
    if (orientation !== 'white' && orientation !== 'black') return;
    this.orientation = orientation;
    this._buildSquares();
    this._refreshHighlightClasses();
  }

  flip() {
    this.setOrientation(this.orientation === 'white' ? 'black' : 'white');
  }

  // -------------------------------------------------------------- controls
  setViewOnly(flag) {
    this.viewOnly = !!flag;
    if (flag) this.setHighlights({});
  }

  getLegalTargets(square) {
    if (!this.opts.getMoves) return [];
    return this.opts.getMoves(square);
  }

  _bindPointer() {
    this.el.addEventListener('pointerdown', (e) => this._onDown(e));
    window.addEventListener('pointermove', (e) => this._onMove(e), { passive: false });
    window.addEventListener('pointerup', (e) => this._onUp(e));
  }

  _squareFromEvent(e) {
    const cell = document.elementFromPoint(e.clientX, e.clientY)?.closest('.square');
    return cell?.dataset.square || null;
  }

  _ownPieceColor() {
    // colour allowed to move pieces; null = both (hotseat)
    return this.opts.movableColor || null;
  }

  _canTouch(piece) {
    if (this.viewOnly) return false;
    const mine = this._ownPieceColor();
    return mine === null || piece.color === mine;
  }

  _onDown(e) {
    if (e.button !== 0 && e.pointerType === 'mouse') return;
    const square = this._squareFromEvent(e);
    if (!square) return;
    e.preventDefault();

    const piece = this.pieces.get(square);

    // clicking a legal target while something is selected -> try the move
    if (this.selected && this.selected !== square
        && this._legalTargets?.includes(square)) {
      this._requestMove(this.selected, square);
      return;
    }

    if (!piece) {
      this.selected = null;
      this.setHighlights({ lastMove: this.lastMove, checkSquare: this.checkSquare });
      return;
    }
    if (!this._canTouch(piece)) return;

    // a simple click just selects the square (legal dots show up);
    // only holding + moving the pointer spawns the drag ghost
    this.selected = square;
    const targets = this.getLegalTargets(square);
    this.setHighlights({
      lastMove: this.lastMove,
      checkSquare: this.checkSquare,
      selected: square,
      legalTargets: targets,
    });

    this.drag = {
      from: square,
      ghost: null,
      startX: e.clientX,
      startY: e.clientY,
      moved: false,
      pointerId: e.pointerId,
    };
  }

  _ensureGhost(e) {
    if (!this.drag || this.drag.ghost) return;
    const piece = this.pieces.get(this.drag.from);
    if (!piece) return;
    const rect = piece.el.getBoundingClientRect();
    const ghost = piece.el.cloneNode(true);
    ghost.classList.add('dragging');
    ghost.style.width = `${rect.width}px`;
    ghost.style.height = `${rect.height}px`;
    document.body.append(ghost);
    this.drag.ghost = ghost;
    piece.el.style.opacity = '0.25';
    this._placeGhost(e);
  }

  _placeGhost(e) {
    if (!this.drag?.ghost) return;
    this.drag.ghost.style.left = `${e.clientX}px`;
    this.drag.ghost.style.top = `${e.clientY}px`;
  }

  _onMove(e) {
    if (!this.drag || e.pointerId !== this.drag.pointerId) return;
    const dx = e.clientX - this.drag.startX;
    const dy = e.clientY - this.drag.startY;
    if (!this.drag.moved && Math.hypot(dx, dy) > 6) {
      this.drag.moved = true;
      this._ensureGhost(e);
    }
    if (this.drag.moved) {
      e.preventDefault();
      this._placeGhost(e);
    }
  }

  _onUp(e) {
    if (!this.drag || e.pointerId !== this.drag.pointerId) return;
    const drag = this.drag;
    this.drag = null;
    const piece = this.pieces.get(drag.from);
    if (piece) piece.el.style.opacity = '';
    drag.ghost?.remove();

    const target = this._squareFromEvent(e);
    if (drag.moved) {
      if (target && target !== drag.from) {
        this._requestMove(drag.from, target);
      } else {
        // keep selection when dropping back
        this.setHighlights({
          lastMove: this.lastMove,
          checkSquare: this.checkSquare,
          selected: drag.from,
          legalTargets: this.getLegalTargets(drag.from),
        });
      }
    }
    // click-click: selection persists until another square is clicked
  }

  async _requestMove(from, to) {
    const legal = this.getLegalTargets(from);
    if (!legal.includes(to)) return;
    const piece = this.pieces.get(from);
    let promotion = null;
    if (piece && piece.type === 'p' && (to[1] === '8' || to[1] === '1')) {
      promotion = await this.askPromotion(piece.color);
      if (!promotion) return;
    }
    const applied = await this.opts.onAttemptMove({ from, to, promotion });
    if (!applied) {
      this.selected = null;
      this.setHighlights({ lastMove: this.lastMove, checkSquare: this.checkSquare });
    }
  }

  askPromotion(color) {
    return new Promise((resolve) => {
      this._promoResolve = resolve;
      const overlay = document.createElement('div');
      overlay.className = 'promo-overlay';
      const row = document.createElement('div');
      row.className = 'promo-row';
      for (const choice of PROMO_CHOICES) {
        const btn = document.createElement('button');
        btn.dataset.choice = choice;
        const img = document.createElement('img');
        img.src = pieceUrl(choice, color);
        img.draggable = false;
        btn.append(img);
        btn.addEventListener('click', () => this._closePromo(choice));
        row.append(btn);
      }
      overlay.append(row);
      overlay.addEventListener('pointerdown', (e) => {
        if (e.target === overlay) this._closePromo(null);
      });
      this.wrap.append(overlay);
      this.promoOverlay = overlay;
    });
  }

  _closePromo(choice) {
    if (this.promoOverlay) {
      this.promoOverlay.remove();
      this.promoOverlay = null;
    }
    const resolve = this._promoResolve;
    this._promoResolve = null;
    resolve?.(choice);
  }
}
