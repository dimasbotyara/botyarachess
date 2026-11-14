"""Chess state services shared by the HTTP API and the SocketIO handlers.

python-chess is the single source of truth: every move, in every mode,
goes through :func:`apply_move` before it reaches a client.
"""
from __future__ import annotations

import random

import chess
import chess.pgn
import io

from ..extensions import db
from ..models import Game, utcnow

TIME_CONTROLS = {
    "none": None,
    "1+0": (60, 0),
    "3+2": (180, 2),
    "5+0": (300, 0),
    "10+0": (600, 0),
}


def board_from_uci(uci_list: list[str]) -> chess.Board:
    """Rebuild a position from a UCI move list."""
    board = chess.Board()
    for uci in uci_list:
        board.push_uci(uci)
    return board


def board_from_game(game: Game) -> chess.Board:
    """Rebuild the current position from the stored UCI move list."""
    return board_from_uci(game.uci_list)


def legal_move_flags(board: chess.Board, move: chess.Move) -> dict:
    """Human-friendly flags describing what kind of move was just played."""
    san = board.san(move)  # SAN before pushing
    return {
        "san": san,
        "capture": board.is_capture(move),
        "castle": board.is_castling(move),
        "check": False,
        "checkmate": False,
        "stalemate": False,
        "game_over": False,
    }


def status_after(board: chess.Board) -> tuple[str, str]:
    """Return (result, termination) for the position *after* a move."""
    if board.is_checkmate():
        return ("1-0" if board.turn == chess.BLACK else "0-1"), "checkmate"
    if board.is_stalemate():
        return "1/2-1/2", "stalemate"
    if board.is_insufficient_material():
        return "1/2-1/2", "insufficient"
    if board.is_fifty_moves():
        return "1/2-1/2", "fifty-move"
    if board.is_repetition(3):
        return "1/2-1/2", "threefold"
    return "*", ""


def apply_move(game: Game, uci_text: str) -> tuple[dict, chess.Board]:
    """Validate and apply a move. Raises ValueError on anything illegal.

    Returns (move_flags, new_board). The caller is responsible for
    persisting the game and finishing it if the result is decided.
    """
    board = board_from_game(game)
    try:
        move = chess.Move.from_uci(uci_text.strip().lower())
    except ValueError as exc:
        raise ValueError("bad-uci") from exc
    if move not in board.legal_moves:
        raise ValueError("illegal")
    if not game.is_active():
        raise ValueError("game-over")

    flags = legal_move_flags(board, move)
    san = flags["san"]
    board.push(move)

    game.moves_uci = (game.moves_uci + " " + move.uci()).strip()
    game.moves_san = (game.moves_san + " " + san).strip()

    result, termination = status_after(board)
    if result != "*":
        flags["game_over"] = True
        flags["check"] = board.is_check()
        finish_game(game, result, termination)
    else:
        flags["check"] = board.is_check()

    return flags, board


def finish_game(game: Game, result: str, termination: str) -> None:
    """Mark a game finished and update the players' stats/ratings."""
    if not game.is_active():
        return
    game.result = result
    game.termination = termination
    game.finished_at = utcnow()

    if game.mode == "online" and game.rated:
        update_ratings(game)
    for color, user in (("white", game.white), ("black", game.black)):
        if user is not None:
            user.record(result, color)
    db.session.commit()


def update_ratings(game: Game, k: int = 20) -> None:
    """Standard Elo with a single K factor for both players."""
    white, black = game.white, game.black
    if white is None or black is None:
        return
    expected_w = 1.0 / (1.0 + 10 ** ((black.rating - white.rating) / 400.0))
    score_w = 0.5 if game.result == "1/2-1/2" else (1.0 if game.result == "1-0" else 0.0)
    white.rating = max(100, round(white.rating + k * (score_w - expected_w)))
    black.rating = max(100, round(black.rating + k * ((1 - score_w) - (1 - expected_w))))


def random_legal_uci(board: chess.Board) -> str | None:
    """Fallback when the AI keeps producing illegal moves."""
    moves = list(board.legal_moves)
    if not moves:
        return None
    captures = [m for m in moves if board.is_capture(m)]
    chosen = random.choice(captures or moves)
    return chosen.uci()


def ascii_board(board: chess.Board) -> str:
    """Unicode-free ASCII representation for LLM prompts (a8 top-left)."""
    symbol = {
        chess.PAWN: "P", chess.KNIGHT: "N", chess.BISHOP: "B",
        chess.ROOK: "R", chess.QUEEN: "Q", chess.KING: "K",
    }
    lines = []
    for rank in range(7, -1, -1):
        row = []
        for file in range(8):
            piece = board.piece_at(chess.square(file, rank))
            if piece is None:
                row.append(".")
            elif piece.color == chess.BLACK:
                row.append(symbol[piece.piece_type].lower())
            else:
                row.append(symbol[piece.piece_type])
        lines.append(f"{rank + 1} | " + " ".join(row))
    lines.append("    a b c d e f g h")
    return "\n".join(lines)


def to_pgn(game: Game) -> str:
    """Serialize a finished (or ongoing) game as a PGN string."""
    board = chess.Board()
    exporter = chess.pgn.StringExporter(columns=80, variations=False, comments=False)
    pgn_game = chess.pgn.Game()
    pgn_game.headers["Event"] = "botyarachess"
    pgn_game.headers["Site"] = "botyarachess local"
    pgn_game.headers["White"] = game.white.username if game.white else "White"
    pgn_game.headers["Black"] = game.black.username if game.black else "Black"
    pgn_game.headers["Date"] = game.started_at.strftime("%Y.%m.%d") if game.started_at else "????.??.??"
    pgn_game.headers["Result"] = game.result
    if game.mode == "ai" and game.ai_provider:
        ai_name = f"AI ({game.ai_provider}"
        if game.ai_model:
            ai_name += f":{game.ai_model}"
        ai_name += ")"
        if game.ai_side == "white":
            pgn_game.headers["White"] = ai_name
        else:
            pgn_game.headers["Black"] = ai_name
    if game.termination:
        pgn_game.headers["Termination"] = game.termination

    node = pgn_game
    for uci in game.uci_list:
        move = chess.Move.from_uci(uci)
        node = node.add_main_variation(move)
        board.push(move)

    return str(pgn_game.accept(exporter))


def state_payload(game: Game, board: chess.Board | None = None,
                  clocks: dict | None = None) -> dict:
    """Canonical JSON snapshot of a game for any client."""
    board = board or board_from_game(game)
    last_uci = game.uci_list[-1] if game.uci_list else None
    return {
        "id": game.id,
        "mode": game.mode,
        "fen": board.fen(),
        "turn": "white" if board.turn == chess.WHITE else "black",
        "moves": [
            {"uci": u, "san": s}
            for u, s in zip(game.uci_list, game.san_list)
        ],
        "last_move": last_uci,
        "check": board.is_check(),
        "status": "active" if game.is_active() else "finished",
        "result": game.result,
        "termination": game.termination,
        "time_control": game.time_control,
        "rated": game.rated,
        "players": game.players_payload(),
        "ai_side": game.ai_side,
        "clocks": clocks,
    }
