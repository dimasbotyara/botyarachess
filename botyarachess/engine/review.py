"""Game review powered by a local chess engine.

Detection order (per requirement):
1. Stockfish, if installed (explicit path -> config -> PATH).
2. GNU Chess, if installed.
3. Neither  -> the review feature reports itself unavailable.

Stockfish speaks UCI; GNU Chess natively speaks the XBoard/CECP protocol,
so both protocols are attempted during the handshake.

Move classification follows the chess.com-style taxonomy:
book / brilliant / great / best / excellent / good / miss /
inaccuracy / mistake / blunder.
"""
from __future__ import annotations

import json
import math
import shutil
import threading

import chess
import chess.engine

from ..config import Config

SPEEDS = {"fast": 0.15, "normal": 0.4, "deep": 1.2}

# In-memory analysis jobs shared with the running Flask process.
_JOBS: dict[str, dict] = {}
_LOCK = threading.Lock()
_JOB_SEQ = 0

MATE_SCORE_CP = 10000


# ---------------------------------------------------------------- opening book
# Small embedded theory book (SAN sequences of popular openings). A move is
# "book" while the played sequence matches one of these lines exactly.
BOOK_LINES = [
    # open games
    "e4 e5 Nf3 Nc6 Bc4 Bc5 c3 Nf6 d3 d6",
    "e4 e5 Nf3 Nc6 Bc4 Nf6 d3 Bc5 c3 O-O",
    "e4 e5 Nf3 Nc6 Bc4 Nf6 Ng5 d5 exd5 Na5",
    "e4 e5 Nf3 Nc6 Bb5 a6 Ba4 Nf6 O-O Be7 Re1 b5 Bb3 d6 c3 O-O h3",
    "e4 e5 Nf3 Nc6 Bb5 Nf6 O-O Nxe4 d4 Nd6 Bxc6 dxc6 dxe5 Nf5",
    "e4 e5 Nf3 Nc6 Nc3 Nf6 Bb5 Bb4 O-O O-O d3 d6",
    "e4 e5 Nf3 Nc6 d4 exd4 Nxd4 Nf6 Nxc6 bxc6 e5 Qe7",
    "e4 e5 Nf3 Nf6 Nxe5 d6 Nf3 Nxe4 d4 d5 Bd3 Be7",
    "e4 e5 f4 exf4 Nf3 g5 h4 g4 Ng5 h6",
    "e4 e5 Nc3 Nf6 f4 d5 fxe5 Nxe4 Nf3 Be7",
    "e4 e5 Bc4 Nf6 d3 c6 Nf3 d5 exd5 cxd5",
    # sicilian
    "e4 c5 Nf3 d6 d4 cxd4 Nxd4 Nf6 Nc3 a6 Be3 e6 f3 b5 g4 h6",
    "e4 c5 Nf3 d6 d4 cxd4 Nxd4 Nf6 Nc3 a6 f3 e5 Bb5+",
    "e4 c5 Nf3 d6 d4 cxd4 Nxd4 Nf6 Nc3 g6 Be3 Bg7 f3 O-O Qd2 Nc6",
    "e4 c5 Nf3 d6 d4 cxd4 Nxd4 Nf6 Nc3 Nc6 Be2 e5 Nb3 Be7",
    "e4 c5 Nf3 e6 d4 cxd4 Nxd4 Nc6 Nc3 Qc7",
    "e4 c5 c3 Nf6 e5 Nd5 d4 cxd4 Nf3 e6",
    "e4 c5 Nc3 Nc6 g3 g6 Bg2 Bg7 d3 d6 Be3 Rb8",
    # french / caro / scandinavian / pirc
    "e4 e6 d4 d5 e5 c5 c3 Nc6 Nf3 Qb6 a3",
    "e4 e6 d4 d5 Nc3 Bb4 e5 c5 a3 Bxc3+ bxc3 Ne7",
    "e4 e6 d4 d5 Nc3 Nf6 e5 Nfd7 f4 c5 Nf3 Nc6 Be3",
    "e4 c6 d4 d5 e5 Bf5 Nf3 e6 Be2 c5",
    "e4 c6 d4 d5 Nc3 dxe4 Nxe4 Bf5 Ng3 Bg6 h4 h6 Nf3 Nd7",
    "e4 c6 d4 d5 exd5 cxd5 Bd3 Nc6 c3 Nf6 Bf4",
    "e4 d5 exd5 Qxd5 Nc3 Qa5 d4 Nf6 Nf3 c6 Bc4 Bf5",
    "e4 d6 d4 Nf6 Nc3 g6 Nf3 Bg7 Be2 O-O O-O c6",
    "e4 Nf6 e5 Nd5 d4 d6 c4 Nb6 exd6 exd6",
    # d4 openings
    "d4 d5 c4 e6 Nc3 Nf6 Bg5 Be7 e3 O-O Nf3 h6 Bh4",
    "d4 d5 c4 e6 Nc3 Nf6 cxd5 exd5 Bg5 c6 e3 Be7 Bd3 O-O",
    "d4 d5 c4 dxc4 Nf3 Nf6 e3 e6 Bxc4 c5 O-O a6",
    "d4 d5 c4 c6 Nf3 Nf6 Nc3 dxc4 a4 Bf5 e3 e6 Bxc4 Bb4",
    "d4 d5 c4 c6 Nf3 Nf6 Nc3 e6 e3 Nbd7 Bd3 dxc4 Bxc4 b5",
    "d4 d5 Nf3 Nf6 Bf4 e6 e3 c5 c3 Nc6 Nbd2 Bd6",
    "d4 Nf6 c4 e6 g3 d5 Bg2 Be7 Nf3 O-O O-O dxc4 Qc2 a6",
    "d4 Nf6 c4 e6 Nc3 Bb4 e3 O-O Bd3 d5 Nf3 c5",
    "d4 Nf6 c4 g6 Nc3 Bg7 e4 d6 Nf3 O-O Be2 e5 O-O Nc6 d5 Ne7",
    "d4 Nf6 c4 g6 Nc3 d5 cxd5 Nxd5 e4 Nxc3 bxc3 Bg7 Bc4 c5 Ne2 Nc6",
    "d4 Nf6 c4 e6 Nf3 c5 d5 exd5 cxd5 d6 Nc3 g6",
    # flank openings
    "c4 e5 Nc3 Nf6 g3 d5 cxd5 Nxd5 Bg2 Nb6",
    "c4 c5 Nc3 Nf6 g3 g6 Bg2 Bg7 Nf3 Nc6 O-O",
    "Nf3 d5 c4 e6 g3 Nf6 Bg2 Be7 O-O O-O b3 c5 Bb2",
    "d4 f5 g3 Nf6 Bg2 e6 Nf3 Be7 O-O O-O",
    "e4 e5 d4 exd4 c3 dxc3 Bc4 cxb2 Bxb2",
]
BOOK: dict[tuple[str, ...], set[str]] = {}
for _line in BOOK_LINES:
    _seq = _line.split()
    for _i in range(len(_seq)):
        BOOK.setdefault(tuple(_seq[:_i]), set()).add(_seq[_i])


# ---------------------------------------------------------------- detect/open
def _which(name: str) -> str | None:
    return shutil.which(name)


def _try_open(path: str, protocol: str):
    """Open an engine with the given protocol; returns (engine, protocol) or (None, None)."""
    try:
        if protocol == "uci":
            return chess.engine.SimpleEngine.popen_uci(path), protocol
        return chess.engine.SimpleEngine.popen_xboard(path), protocol
    except Exception:  # noqa: BLE001 - anything from missing binary to bad handshake
        return None, None


def open_engine() -> tuple[chess.engine.SimpleEngine, str, str] | None:
    """Detect and open the best available engine. Returns (engine, name, protocol)."""
    candidates: list[tuple[str, str | None]] = []
    if Config.STOCKFISH_PATH:
        candidates.append(("stockfish", Config.STOCKFISH_PATH))
    if Config.GNUCHESS_PATH:
        candidates.append(("gnuchess", Config.GNUCHESS_PATH))
    for name in ("stockfish", "stockfish.exe"):
        found = _which(name)
        if found:
            candidates.append(("stockfish", found))
            break
    for name in ("gnuchess", "gnuchess.exe"):
        found = _which(name)
        if found:
            candidates.append(("gnuchess", found))
            break

    for name, path in candidates:
        protocols = ("uci",) if name == "stockfish" else ("uci", "xboard")
        for protocol in protocols:
            engine, opened = _try_open(path, protocol)
            if engine:
                return engine, name, opened
    return None


def engine_status() -> dict:
    """Public status for the settings page and review gating."""
    opened = open_engine()
    if opened:
        engine, name, _ = opened
        try:
            engine.quit()
        except chess.engine.EngineError:
            pass
        return {"available": True, "name": name}
    return {"available": False, "name": None}


# -------------------------------------------------------------------- helpers
def win_percent(cp: float) -> float:
    """Lichess win-percentage model: centipawns -> [0, 100]."""
    return 50.0 + 50.0 * (2.0 / (1.0 + math.exp(-0.00368208 * cp)) - 1.0)


def move_accuracy(wp_before: float, wp_after: float) -> float:
    """Lichess-style per-move accuracy from the win% drop."""
    drop = max(0.0, wp_before - wp_after)
    value = 103.1668 * math.exp(-0.04354 * drop) - 3.1669
    return max(0.0, min(100.0, value))


def _white_cp(info: dict, mover: chess.Color) -> float:
    """Score from an analyse() info dict, converted to white perspective (pawns)."""
    score = info.get("score")
    if score is None:
        return 0.0
    try:
        relative = score.relative.score(mate_score=MATE_SCORE_CP)
    except Exception:
        return 0.0
    cp = relative if mover == chess.WHITE else -relative
    return float(max(-1500, min(1500, cp)))


def _material_pawns(board: chess.Board, color: chess.Color) -> float:
    """Material of one side in pawn units."""
    values = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3,
              chess.ROOK: 5, chess.QUEEN: 9}
    total = 0.0
    for piece_type, value in values.items():
        total += value * len(board.pieces(piece_type, color))
    return total


def _classify_ply(*, is_book: bool, played_best: bool, cpl: int, wpl: float,
                  gap: float | None, sacrifice_pawns: float,
                  mover_before: float, mover_after: float) -> str:
    """chess.com-style classification for a single move (mover perspective).

    All eval inputs are in pawns from the mover's point of view.
    """
    if is_book:
        return "book"
    if played_best or wpl <= 1:
        if sacrifice_pawns >= 1.5 and mover_after >= 0.3:
            return "brilliant"
        # "great" = rare only-move; meaningless when the position is already
        # completely decided (then a matching move is simply "best")
        if gap is not None and gap >= 1.5 and mover_after >= -0.5 \
                and mover_before <= 5.0:
            return "great"
        return "best"
    if wpl <= 2:
        return "excellent"
    if wpl <= 5:
        return "good"
    if mover_before >= 2.0 and mover_after <= 0.8:
        return "miss"  # had a winning position and let it slip
    if wpl <= 10:
        return "inaccuracy"
    if wpl <= 20:
        return "mistake"
    return "blunder"


# ------------------------------------------------------------------- analysis
def analyze_game(game, speed: str = "normal", progress=None) -> dict:
    """Blocking full-game analysis; must run in a background thread.

    `progress(done, total)` is called after each ply.
    """
    opened = open_engine()
    if opened is None:
        raise RuntimeError("no-engine")
    engine, name, _ = opened

    per_move = SPEEDS.get(speed, SPEEDS["normal"])
    limit = chess.engine.Limit(time=per_move)

    try:
        if name == "stockfish":
            engine.configure({"Threads": 1})

        board = chess.Board()
        plies: list[dict] = []
        uci_moves = game.uci_list
        total = max(1, len(uci_moves))
        accuracy_by_color: dict[str, list[float]] = {"white": [], "black": []}
        san_history: list[str] = []

        for index, uci in enumerate(uci_moves):
            mover = board.turn

            # Best move(s) + score in the position BEFORE the played move.
            infos = None
            try:
                infos = engine.analyse(board, limit, multipv=2,
                                       info=chess.engine.INFO_ALL)
            except Exception:
                infos = None
            if not isinstance(infos, list):
                infos = [engine.analyse(board, limit, info=chess.engine.INFO_ALL)]

            best_cp = _white_cp(infos[0], mover)
            pv = infos[0].get("pv") or []
            best_uci = pv[0].uci() if pv else None
            gap: float | None = None
            if len(infos) > 1:
                second_cp = _white_cp(infos[1], mover)
                best_for_mover_probe = best_cp if mover == chess.WHITE else -best_cp
                second_for_mover = second_cp if mover == chess.WHITE else -second_cp
                gap = max(0.0, best_for_mover_probe - second_for_mover)

            try:
                move = chess.Move.from_uci(uci)
            except ValueError:
                move = None
            played_san = board.san(move) if move in board.legal_moves else uci

            material_before = _material_pawns(board, mover)

            # Score + material in the position AFTER the played move.
            # Note: after the push it is the opponent's turn, so the relative
            # score must be converted from THEIR side of the board.
            after_cp = 0.0
            material_after = material_before
            if move is not None and move in board.legal_moves:
                board.push(move)
                info_after = engine.analyse(board, limit, info=chess.engine.INFO_ALL)
                after_cp = _white_cp(info_after, board.turn)
                material_after = _material_pawns(board, mover)
            else:
                move = None

            # Centipawn / win-percentage loss from the mover's point of view.
            best_for_mover = best_cp if mover == chess.WHITE else -best_cp
            after_for_mover = after_cp if mover == chess.WHITE else -after_cp
            cpl = int(max(0.0, best_for_mover - after_for_mover))
            played_best = uci == best_uci or cpl <= 2
            wpl = win_percent(best_for_mover) - win_percent(after_for_mover)

            is_book = played_san in BOOK.get(tuple(san_history), set())

            cls = _classify_ply(
                is_book=is_book,
                played_best=played_best,
                cpl=cpl,
                wpl=wpl,
                gap=gap,
                sacrifice_pawns=material_before - material_after,
                mover_before=best_for_mover / 100.0,
                mover_after=after_for_mover / 100.0,
            )

            wp_before = win_percent(best_for_mover)
            wp_after = win_percent(after_for_mover)
            accuracy = move_accuracy(wp_before, wp_after)
            color_key = "white" if mover == chess.WHITE else "black"
            accuracy_by_color[color_key].append(accuracy)

            plies.append({
                "ply": index + 1,
                "uci": uci,
                "san": played_san,
                "eval_after": round(after_cp / 100.0, 2),
                "best_uci": best_uci,
                "cpl": cpl,
                "class": cls,
                "accuracy": round(accuracy, 1),
            })

            san_history.append(played_san)
            if progress:
                progress(index + 1, total)

        def mean(values: list[float]) -> float:
            return round(sum(values) / len(values), 1) if values else 0.0

        return {
            "engine": name,
            "speed": speed,
            "accuracy": {"white": mean(accuracy_by_color["white"]),
                         "black": mean(accuracy_by_color["black"])},
            "plies": plies,
        }
    finally:
        try:
            engine.quit()
        except chess.engine.EngineError:
            pass


# ----------------------------------------------------------------- job runner
def _running_job_for_game(game_id: int) -> str | None:
    for job_id, job in _JOBS.items():
        if job.get("game_id") == game_id and not job.get("done"):
            return job_id
    return None


def start_review(app, game, speed: str = "normal") -> dict:
    """Kick off a background analysis; returns job info immediately.

    Must be called from inside an app context (it touches the DB row).
    """
    global _JOB_SEQ
    opened = open_engine()
    if opened is None:
        return {"available": False}
    try:
        opened[0].quit()
    except chess.engine.EngineError:
        pass

    with _LOCK:
        existing = _running_job_for_game(game.id)
        if existing:
            return {"available": True, "job_id": existing, "running": True}
        _JOB_SEQ += 1
        job_id = f"rev{_JOB_SEQ}"
        _JOBS[job_id] = {
            "job_id": job_id,
            "game_id": game.id,
            "speed": speed,
            "progress": 0,
            "done": False,
            "error": None,
        }

    from ..extensions import db as _db  # bound later, needs app context anyway
    from ..models import Game as _Game

    game_id = game.id

    def runner() -> None:
        with app.app_context():
            try:
                # re-fetch in THIS session: the request-scoped object is detached here
                fresh_game = _db.session.get(_Game, game_id)
                result = analyze_game(
                    fresh_game, speed,
                    progress=lambda done, tot: _set_progress(job_id, done, tot),
                )
                fresh_game.analysis_json = json.dumps(result, ensure_ascii=False)
                _db.session.commit()
                with _LOCK:
                    _JOBS[job_id].update(done=True, progress=100)
            except Exception as exc:  # noqa: BLE001 - surfaced to the client
                with _LOCK:
                    _JOBS[job_id].update(done=True, error=str(exc) or exc.__class__.__name__)

    threading.Thread(target=runner, daemon=True, name=f"review-{job_id}").start()
    return {"available": True, "job_id": job_id, "running": True}


def _set_progress(job_id: str, done: int, total: int) -> None:
    with _LOCK:
        if job_id in _JOBS:
            _JOBS[job_id]["progress"] = int(done / max(1, total) * 100)


def job_status(job_id: str) -> dict | None:
    with _LOCK:
        job = _JOBS.get(job_id)
        return dict(job) if job else None
