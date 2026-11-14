"""Game review powered by a local chess engine.

Detection order (per requirement):
1. Stockfish, if installed (explicit path -> config -> PATH).
2. GNU Chess, if installed.
3. Neither  -> the review feature reports itself unavailable.

Stockfish speaks UCI; GNU Chess natively speaks the XBoard/CECP protocol,
so both protocols are attempted during the handshake.
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
        # Stockfish is UCI-only; gnuchess may answer either protocol.
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


# ------------------------------------------------------------------ analysis
def win_percent(cp: float) -> float:
    """Lichess win-percentage model: centipawns -> [0, 100]."""
    return 50.0 + 50.0 * (2.0 / (1.0 + math.exp(-0.00368208 * cp)) - 1.0)


def move_accuracy(wp_before: float, wp_after: float) -> float:
    """Lichess-style per-move accuracy from the win% drop."""
    drop = max(0.0, wp_before - wp_after)
    value = 103.1668 * math.exp(-0.04354 * drop) - 3.1669
    return max(0.0, min(100.0, value))


def classify(cpl: int, played_best: bool) -> str:
    """Human classification from centipawn loss (mover's perspective)."""
    if played_best:
        return "best"
    if cpl <= 10:
        return "excellent"
    if cpl <= 25:
        return "good"
    if cpl <= 50:
        return "inaccuracy"
    if cpl <= 120:
        return "mistake"
    return "blunder"


def _white_cp(info: dict, mover: chess.Color) -> float:
    """Score from an analyse() info dict, converted to white perspective (pawns)."""
    score = info.get("score")
    if score is None:
        return 0.0
    try:
        relative = score.relative.score(mate_score=10000)
    except Exception:
        return 0.0
    cp = relative if mover == chess.WHITE else -relative
    return float(max(-1500, min(1500, cp)))


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

        for index, uci in enumerate(uci_moves):
            # Best move + score in the position BEFORE the played move.
            info = engine.analyse(board, limit, info=chess.engine.INFO_SCORE)
            mover = board.turn
            best_cp = _white_cp(info, mover)
            pv = info.get("pv") or []
            best_uci = pv[0].uci() if pv else None

            try:
                move = chess.Move.from_uci(uci)
            except ValueError:
                move = None
            played_san = board.san(move) if move in board.legal_moves else uci

            # Score in the position AFTER the played move.
            after_cp = 0.0
            if move is not None and move in board.legal_moves:
                board.push(move)
                info_after = engine.analyse(board, limit, info=chess.engine.INFO_SCORE)
                after_cp = _white_cp(info_after, mover)
            else:
                move = None

            # Centipawn loss from the mover's point of view.
            best_for_mover = best_cp if mover == chess.WHITE else -best_cp
            after_for_mover = after_cp if mover == chess.WHITE else -after_cp
            cpl = int(max(0.0, best_for_mover - after_for_mover))
            played_best = uci == best_uci or cpl <= 2

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
                "class": classify(cpl, played_best),
                "accuracy": round(accuracy, 1),
            })

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
