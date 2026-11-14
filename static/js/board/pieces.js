// Chess piece SVG assets (local Cburnett set under /static/img/pieces/).

const LETTERS = { p: 'P', n: 'N', b: 'B', r: 'R', q: 'Q', k: 'K' };

export function pieceUrl(type, color) {
  // type: 'p'|'n'|'b'|'r'|'q'|'k' (chess.js), color: 'w'|'b'
  return `/static/img/pieces/${color}${LETTERS[type]}.svg`;
}

/** Preload all 12 piece images so first drag/flip never flashes. */
export function preloadPieces() {
  for (const color of ['w', 'b']) {
    for (const key of Object.values(LETTERS)) {
      const img = new Image();
      img.src = `/static/img/pieces/${color}${key}.svg`;
    }
  }
}
