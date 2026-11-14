// Review page: stepper board, eval graph, move classifications.
import { Chess } from '../../vendor/chess.js';
import { ChessBoardUI } from '../board/board.js';
import { preloadPieces } from '../board/pieces.js';
import { api } from '../core/api.js';
import { el, toastError } from '../core/ui.js';
import { t } from '../core/i18n.js';
import { icon } from '../core/icons.js';
import { sounds, unlockAudio } from '../core/sounds.js';

preloadPieces();
unlockAudio();

const CLASS_ICON = {
  book: 'book-open',
  brilliant: 'gem',
  great: 'sparkles',
  best: 'crown',
  excellent: 'star',
  good: 'check',
  miss: 'target',
  inaccuracy: 'info',
  mistake: 'triangle-alert',
  blunder: 'flame',
};

function classTooltip(cls) {
  const desc = t(`review.class.${cls}_desc`);
  return `${t('review.class.' + cls)} — ${desc}`;
}

const root = document.getElementById('review-root');
const gameData = JSON.parse(root.dataset.game);
const plies = gameData.moves;
const engineAvailable = root.dataset.engine === '1';

const board = new ChessBoardUI(document.getElementById('board'), {
  orientation: 'white',
  coords: true,
  viewOnly: true,
  highlightLegal: false,
});

let currentPly = plies.length;
let analysis = null;

function positionAfter(n) {
  const chess = new Chess();
  for (let i = 0; i < n; i += 1) chess.move(plies[i]); // raw SAN strings
  return chess;
}

function showPly(n) {
  currentPly = Math.max(0, Math.min(n, plies.length));
  const chess = positionAfter(currentPly);
  board.setPosition(chess.fen(), { animate: true });
  if (currentPly > 0) {
    const last = pliesData()[currentPly - 1];
    const uci = last.uci || '';
    if (uci.length >= 4) {
      board.setHighlights({ lastMove: { from: uci.slice(0, 2), to: uci.slice(2, 4) } });
    } else {
      board.setHighlights({});
    }
  } else {
    board.setHighlights({});
  }
  // ply indicator between the arrows
  const plyNode = document.getElementById('nav-ply');
  if (plyNode) plyNode.textContent = `${currentPly} / ${plies.length}`;
  document.querySelectorAll('.review-moves .move').forEach((node) => {
    node.classList.toggle('current', Number(node.dataset.ply) === currentPly);
  });
  const current = analysis?.plies?.[currentPly - 1];
  const evalNode = document.getElementById('eval-info');
  if (evalNode) {
    if (current) {
      const cls = current['class'];
      const clsIcon = CLASS_ICON[cls] || 'info';
      const label = `<span class="cls-${cls}" style="display:inline-flex;align-items:center;gap:5px">
        <span class="cls-icon">${icon(clsIcon)}</span>${t('review.class.' + cls)}</span>`;
      evalNode.innerHTML = `${t('review.evaluation')}: ${current.eval_after > 0 ? '+' : ''}${current.eval_after} · ${label}`;
    } else {
      evalNode.textContent = '';
    }
  }
}

/** Analysis plies when available; plain SAN entries before that. */
function pliesData() {
  if (analysis && analysis.plies) return analysis.plies;
  return plies.map((san, i) => ({ ply: i + 1, san }));
}

function buildMoveList() {
  const list = document.getElementById('review-moves-list');
  if (!list) return;
  list.innerHTML = '';
  const data = pliesData();
  for (let i = 0; i < data.length; i += 2) {
    const cells = [data[i], data[i + 1]];
    const row = el('li', {}, el('span.move-num', {}, `${i / 2 + 1}.`));
    cells.forEach((move) => {
      if (!move) { row.append(el('span.move', {}, '')); return; }
      const cls = move['class'] || null;
      const node = el(`span.move${cls ? ' cls-' + cls : ''}`, {
        dataset: { ply: move.ply },
        onclick: () => showPly(move.ply),
        title: cls ? classTooltip(cls) : '',
      }, move.san);
      if (cls && analysis) {
        const holder = el('span.cls-icon');
        holder.innerHTML = icon(CLASS_ICON[cls] || 'info');
        node.append(holder);
      }
      row.append(node);
    });
    list.append(row);
  }
  showPly(currentPly);
}

function drawGraph() {
  const canvas = document.getElementById('eval-graph');
  if (!canvas || !analysis) return;
  const ctx = canvas.getContext('2d');
  const width = canvas.width = canvas.clientWidth * (window.devicePixelRatio || 1);
  const height = canvas.height = canvas.clientHeight * (window.devicePixelRatio || 1);
  ctx.scale(1, 1);

  const evals = [0, ...analysis.plies.map((p) => Math.max(-10, Math.min(10, p.eval_after)))];
  const maxEval = 10;
  const toY = (value) => height / 2 - (value / maxEval) * (height / 2 - 6);

  const styles = getComputedStyle(document.documentElement);
  const accent = styles.getPropertyValue('--accent').trim() || '#888';
  const border = styles.getPropertyValue('--border').trim() || '#444';

  ctx.clearRect(0, 0, width, height);
  // middle line
  ctx.strokeStyle = border;
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(0, height / 2);
  ctx.lineTo(width, height / 2);
  ctx.stroke();

  // area
  const stepX = width / Math.max(1, evals.length - 1);
  ctx.beginPath();
  ctx.moveTo(0, toY(evals[0]));
  evals.forEach((value, i) => ctx.lineTo(i * stepX, toY(value)));
  ctx.lineTo(width, height / 2);
  ctx.lineTo(0, height / 2);
  ctx.closePath();
  ctx.fillStyle = accent + '55';
  ctx.fill();

  // line
  ctx.beginPath();
  ctx.moveTo(0, toY(evals[0]));
  evals.forEach((value, i) => ctx.lineTo(i * stepX, toY(value)));
  ctx.strokeStyle = accent;
  ctx.lineWidth = 2;
  ctx.stroke();

  // current position marker
  if (currentPly > 0) {
    const x = currentPly * stepX;
    ctx.fillStyle = styles.getPropertyValue('--danger').trim() || 'red';
    ctx.beginPath();
    ctx.arc(x, toY(evals[currentPly] ?? 0), 4, 0, Math.PI * 2);
    ctx.fill();
  }
}

function renderAnalysis() {
  document.getElementById('review-loading')?.classList.add('hidden');
  document.getElementById('review-content')?.classList.remove('hidden');
  document.getElementById('engine-name').innerHTML =
    `${icon('cpu')} ${t('review.engine')}: ${analysis.engine}`;
  const acc = analysis.accuracy;
  document.getElementById('acc-white-bar').style.width = `${acc.white}%`;
  document.getElementById('acc-black-bar').style.width = `${acc.black}%`;
  document.getElementById('acc-white-value').textContent = `${acc.white}%`;
  document.getElementById('acc-black-value').textContent = `${acc.black}%`;
  buildMoveList();
  drawGraph();
}

function myColor() {
  return root.dataset.myColor || 'white';
}

async function loadExisting() {
  try {
    const data = await api(`/api/games/${gameData.id}/analysis`);
    if (data.analysis) {
      analysis = data.analysis;
      renderAnalysis();
    }
  } catch { /* no analysis yet */ }
}

async function startReview(speed) {
  const progressNode = document.getElementById('review-progress');
  try {
    const start = await api(`/api/games/${gameData.id}/review/start`, {
      method: 'POST', body: { speed },
    });
    if (!start.available) {
      progressNode.textContent = t('review.unavailable');
      return;
    }
    progressNode.textContent = t('review.progress', { p: 0 });
    const poll = setInterval(async () => {
      const status = await api(`/api/review/status/${start.job_id}`);
      if (status.error) { clearInterval(poll); return; }
      progressNode.textContent = t('review.progress', { p: status.progress });
      if (status.done && !status.error) {
        clearInterval(poll);
        const data = await api(`/api/games/${gameData.id}/analysis`);
        if (data.analysis) {
          analysis = data.analysis;
          renderAnalysis();
        }
        progressNode.textContent = '';
      } else if (status.error) {
        clearInterval(poll);
        toastError(status.error);
        progressNode.textContent = '';
      }
    }, 700);
  } catch (error) { toastError(error); }
}

// controls
document.getElementById('btn-prev')?.addEventListener('click', () => showPly(currentPly - 1));
document.getElementById('btn-next')?.addEventListener('click', () => showPly(currentPly + 1));
document.getElementById('btn-start')?.addEventListener('click', () => showPly(0));
document.getElementById('btn-end')?.addEventListener('click', () => showPly(plies.length));
document.addEventListener('keydown', (e) => {
  if (e.key === 'ArrowLeft') showPly(currentPly - 1);
  if (e.key === 'ArrowRight') showPly(currentPly + 1);
});
document.getElementById('btn-review-start')?.addEventListener('click', () => {
  if (!engineAvailable) {
    toastError('review.unavailable');
    return;
  }
  const speed = document.getElementById('review-speed')?.value || 'normal';
  startReview(speed);
});

if (engineAvailable) {
  document.getElementById('review-speed')?.classList.remove('hidden');
  document.getElementById('btn-review-start')?.classList.remove('hidden');
} else {
  const node = document.getElementById('review-unavailable');
  node?.classList.remove('hidden');
}

loadExisting();
buildMoveList();
window.addEventListener('resize', drawGraph);
