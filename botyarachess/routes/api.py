"""JSON API: settings, hotseat/AI games, moves, history, PGN, review jobs."""
from __future__ import annotations

import json as _json

import chess
from flask import Blueprint, Response, abort, jsonify, request
from flask_login import current_user, login_required

from ..ai import opponent, providers
from ..config import Config
from ..engine import review
from ..extensions import db
from ..games import service
from ..localization.strings import locale_for
from ..models import ChatMessage, Game, User

api_bp = Blueprint("api", __name__, url_prefix="/api")

VALID_SPEEDS = ("fast", "normal", "deep")


# ------------------------------------------------------------------ account
@api_bp.get("/me")
@login_required
def me():
    return jsonify({
        "id": current_user.id,
        "username": current_user.username,
        "rating": current_user.rating,
        "theme": current_user.theme,
        "locale": current_user.locale or None,
        "settings": current_user.settings,
        "ai": current_user.masked_ai(),
    })


@api_bp.post("/settings")
@login_required
def save_settings():
    data = request.get_json(silent=True) or {}
    if "theme" in data:
        current_user.theme = str(data["theme"])[:32]
    if "locale" in data:
        locale = str(data["locale"])
        current_user.locale = locale if locale in ("ru", "en") else ""
    settings_patch = data.get("settings")
    if isinstance(settings_patch, dict):
        current_user.update_settings(settings_patch)
    db.session.commit()
    return jsonify(ok=True)


@api_bp.get("/settings/ai")
@login_required
def get_ai_settings():
    return jsonify(current_user.masked_ai())


@api_bp.post("/settings/ai")
@login_required
def save_ai_settings():
    data = request.get_json(silent=True) or {}
    patch = {}
    for key in ("provider", "model", "base_url", "lm_host", "persona",
                "persona_custom"):
        if key in data:
            patch[key] = str(data[key])[:200]
    if "lm_port" in data:
        try:
            patch["lm_port"] = int(data["lm_port"])
        except (TypeError, ValueError):
            return jsonify(error="invalid_input"), 400
    if "temperature" in data:
        try:
            patch["temperature"] = min(2.0, max(0.0, float(data["temperature"])))
        except (TypeError, ValueError):
            return jsonify(error="invalid_input"), 400
    if "chat_enabled" in data:
        patch["chat_enabled"] = bool(data["chat_enabled"])
    if "api_key" in data:
        key = str(data["api_key"])
        if key == "__clear__":
            patch["api_key"] = ""
        elif key.strip() and not key.startswith("••"):
            patch["api_key"] = key.strip()
    current_user.update_ai(patch)
    db.session.commit()
    return jsonify(ok=True, ai=current_user.masked_ai())


@api_bp.post("/ai/test")
@login_required
def test_ai():
    """Connection smoke test with either saved config or submitted overrides."""
    data = request.get_json(silent=True) or {}
    saved = current_user.ai
    if data.get("use_saved") or not data:
        cfg = dict(saved)
    else:
        cfg = dict(saved)
        for key in ("provider", "model", "base_url", "lm_host", "lm_port",
                    "api_key", "temperature"):
            if key in data and data[key] not in (None, ""):
                cfg[key] = data[key]
        if data.get("api_key") == "__clear__":
            cfg["api_key"] = ""
    if cfg.get("provider") == "manual":
        return jsonify(ok=True, raw="manual mode: nothing to test"), 200
    try:
        result = providers.test_connection(cfg)
    except providers.AIProviderError as exc:
        return jsonify(ok=False, error=str(exc)), 200
    return jsonify(result), 200


# ------------------------------------------------------------------ security
@api_bp.post("/security/password")
@login_required
def change_password():
    from werkzeug.security import check_password_hash

    data = request.get_json(silent=True) or {}
    current = str(data.get("current") or "")
    new = str(data.get("new") or "")
    if not current_user.check_password(current):
        return jsonify(error="wrong_current_password"), 400
    if len(new) < 6:
        return jsonify(error="password_len"), 400
    current_user.set_password(new)
    db.session.commit()
    return jsonify(ok=True)


@api_bp.post("/security/delete_account")
@login_required
def delete_account():
    """Requires the exact username as typed confirmation."""
    from flask_login import logout_user

    data = request.get_json(silent=True) or {}
    confirm = str(data.get("confirm") or "").strip()
    if confirm != current_user.username:
        return jsonify(error="confirm_mismatch"), 400

    user_id = current_user.id
    Game.query.filter(Game.white_id == user_id).update({"white_id": None})
    Game.query.filter(Game.black_id == user_id).update({"black_id": None})
    user = db.session.get(User, user_id)
    db.session.delete(user)
    db.session.commit()
    logout_user()
    return jsonify(ok=True)


@api_bp.get("/export")
@login_required
def export_data():
    """Personal data dump: account, settings and every game with its chat."""
    games = (Game.query
             .filter((Game.white_id == current_user.id) |
                     (Game.black_id == current_user.id))
             .order_by(Game.started_at.desc()).all())
    payload = {
        "account": {
            "username": current_user.username,
            "created_at": current_user.created_at.isoformat(),
            "rating": current_user.rating,
            "stats": {"wins": current_user.wins, "losses": current_user.losses,
                      "draws": current_user.draws},
            "settings": current_user.settings,
            "ai": current_user.masked_ai(),
        },
        "games": [
            {
                "id": g.id, "mode": g.mode, "result": g.result,
                "termination": g.termination, "rated": g.rated,
                "time_control": g.time_control,
                "started_at": g.started_at.isoformat() if g.started_at else None,
                "moves_uci": g.uci_list, "moves_san": g.san_list,
                "chat": [m.payload() for m in g.messages],
            }
            for g in games
        ],
    }
    body = _json.dumps(payload, ensure_ascii=False, indent=2)
    return Response(
        body,
        mimetype="application/json",
        headers={"Content-Disposition":
                 f"attachment; filename=botyarachess-{current_user.username}.json"},
    )


# -------------------------------------------------------------------- games
def _get_game_or_404(game_id: int, players_only: bool = True) -> Game:
    game = db.session.get(Game, game_id)
    if game is None:
        abort(404)
    if players_only and not game.is_player(current_user.id):
        abort(403)
    return game


@api_bp.post("/games/hotseat")
@login_required
def create_hotseat():
    game = Game(mode="hotseat", white_id=current_user.id, black_id=current_user.id)
    db.session.add(game)
    db.session.commit()
    return jsonify(game_id=game.id)


@api_bp.post("/games/ai")
@login_required
def create_ai():
    data = request.get_json(silent=True) or {}
    color = data.get("color", "white")
    if color == "random":
        import random
        color = random.choice(("white", "black"))
    if color not in ("white", "black"):
        color = "white"
    ai_side = "black" if color == "white" else "white"
    ai_cfg = current_user.masked_ai()
    game = Game(
        mode="ai",
        white_id=current_user.id if color == "white" else None,
        black_id=current_user.id if color == "black" else None,
        ai_side=ai_side,
        ai_provider=ai_cfg.get("provider", "manual"),
        ai_model=ai_cfg.get("model", ""),
    )
    db.session.add(game)
    db.session.commit()
    return jsonify(game_id=game.id)


@api_bp.get("/games")
@login_required
def list_games():
    items = (Game.query
             .filter((Game.white_id == current_user.id) |
                     (Game.black_id == current_user.id))
             .order_by(Game.started_at.desc())
             .limit(100).all())
    return jsonify({"games": [_game_brief(g) for g in items]})


def _game_brief(game: Game) -> dict:
    return {
        "id": game.id,
        "mode": game.mode,
        "result": game.result,
        "termination": game.termination,
        "time_control": game.time_control,
        "rated": game.rated,
        "started_at": game.started_at.isoformat() if game.started_at else None,
        "finished_at": game.finished_at.isoformat() if game.finished_at else None,
        "moves": len(game.uci_list),
        "white": game.white.username if game.white else "AI",
        "black": game.black.username if game.black else "AI",
        "has_analysis": bool(game.analysis_json),
    }


@api_bp.get("/games/<int:game_id>")
@login_required
def game_state(game_id: int):
    game = _get_game_or_404(game_id, players_only=False)
    if not game.is_player(current_user.id) and game.mode != "online":
        abort(403)
    from ..games.manager import LOBBY, clocks_payload
    room = LOBBY.get_room(game_id)
    payload = service.state_payload(game, clocks=clocks_payload(room) if room else None)
    payload["my_color"] = game.color_of(current_user.id)
    if game.mode == "ai":
        payload["chat"] = [m.payload() for m in game.messages.limit(200)]
    return jsonify(payload)


# ------------------------------------------------------------- move handling
@api_bp.post("/games/<int:game_id>/move")
@login_required
def post_move(game_id: int):
    game = _get_game_or_404(game_id)
    if game.mode == "online":
        return jsonify(error="use-socket"), 400
    data = request.get_json(silent=True) or {}
    uci = str(data.get("uci") or "").strip()
    message = str(data.get("message") or "").strip()

    board = service.board_from_game(game)
    my_color = game.color_of(current_user.id) or "white"

    # A player move (empty uci means "just ask the AI to move/start").
    if uci:
        if not game.is_active():
            return jsonify(error="game_over"), 400
        if game.mode != "hotseat":
            # in hotseat one account plays both sides; legal_moves still rules
            expected_turn = chess.WHITE if my_color == "white" else chess.BLACK
            if board.turn != expected_turn:
                return jsonify(error="not_your_turn"), 400
        try:
            flags, board = service.apply_move(game, uci)
        except ValueError as exc:
            return jsonify(error=f"invalid_{exc}"), 400
        db.session.commit()
        if flags.get("game_over"):
            return jsonify(_move_response(game, board, flags, None))

    # Now possibly the AI's turn.
    ai_payload = None
    if game.mode == "ai" and game.is_active():
        ai_color = game.ai_side or "black"
        ai_turn = board.turn == (chess.WHITE if ai_color == "white" else chess.BLACK)
        if ai_turn:
            ai_payload = _run_ai_turn(game, message)

    return jsonify(_move_response(game, board, {}, ai_payload))


def _run_ai_turn(game: Game, player_message: str | None) -> dict | None:
    """Let the AI answer; returns its move/chat or a manual-mode marker."""
    cfg = current_user.masked_ai()
    if (cfg.get("provider") or "manual") == "manual":
        if player_message:
            opponent.persist_player_chat(game, player_message)
        return {"need_prompt": True}

    if player_message:
        opponent.persist_player_chat(game, player_message)

    board = service.board_from_game(game)
    result = opponent.make_ai_move(game, board, player_message)
    if result.move is None:
        return {"ai_chat": result.chat, "ai_chat_kind": result.chat_kind,
                "ai_failed": True}

    flags, board = service.apply_move(game, result.move.uci())
    opponent.persist_ai_chat(game, result.chat, result.chat_kind)
    db.session.commit()
    return {
        "ai_move": {"uci": result.move.uci(), "san": flags["san"]},
        "ai_chat": result.chat,
        "ai_chat_kind": result.chat_kind,
        "ai_attempts": result.attempts,
        "ai_fallback": result.used_fallback,
        "flags": {k: v for k, v in flags.items() if k != "san"},
    }


def _move_response(game: Game, board, flags: dict, ai_payload: dict | None) -> dict:
    payload = service.state_payload(game, board=board)
    payload["flags"] = {k: v for k, v in flags.items() if k != "san"}
    if ai_payload:
        payload.update(ai_payload)
    if game.mode == "ai":
        payload["chat"] = [m.payload() for m in game.messages.limit(200)]
    payload["my_color"] = game.color_of(current_user.id)
    return payload


@api_bp.post("/games/<int:game_id>/resign")
@login_required
def resign(game_id: int):
    game = _get_game_or_404(game_id)
    if not game.is_active():
        return jsonify(error="game_over"), 400
    color = game.color_of(current_user.id) or "white"
    result = "0-1" if color == "white" else "1-0"
    service.finish_game(game, result, "resign")
    board = service.board_from_game(game)
    return jsonify(service.state_payload(game, board=board))


@api_bp.post("/games/<int:game_id>/undo")
@login_required
def undo(game_id: int):
    game = _get_game_or_404(game_id)
    if game.mode == "online":
        return jsonify(error="use-socket"), 400
    if not game.is_active():
        return jsonify(error="game_over"), 400
    my_color = game.color_of(current_user.id) or "white"
    uci = game.uci_list
    san = game.san_list

    # Remove plies until it is the player's turn again.
    while uci:
        uci.pop()
        san.pop()
        board = service.board_from_uci(uci)
        turn = "white" if board.turn == chess.WHITE else "black"
        if game.mode != "ai" or turn == my_color:
            break
    game.moves_uci = " ".join(uci)
    game.moves_san = " ".join(san)
    db.session.commit()
    return jsonify(service.state_payload(game))


@api_bp.get("/games/<int:game_id>/pgn")
@login_required
def download_pgn(game_id: int):
    game = _get_game_or_404(game_id, players_only=False)
    if not game.is_player(current_user.id) and game.mode != "online":
        abort(403)
    text = service.to_pgn(game)
    return Response(
        text,
        mimetype="application/x-chess-pgn",
        headers={"Content-Disposition": f"attachment; filename=botyarachess-{game.id}.pgn"},
    )


# --------------------------------------------------------------- manual mode
@api_bp.get("/games/<int:game_id>/manual_prompt")
@login_required
def manual_prompt(game_id: int):
    game = _get_game_or_404(game_id)
    if game.mode != "ai":
        return jsonify(error="not_ai"), 400
    board = service.board_from_game(game)
    return jsonify(prompt=opponent.build_manual_prompt(game, board))


@api_bp.post("/games/<int:game_id>/manual_reply")
@login_required
def manual_reply(game_id: int):
    game = _get_game_or_404(game_id)
    if game.mode != "ai":
        return jsonify(error="not_ai"), 400
    data = request.get_json(silent=True) or {}
    text = str(data.get("text") or "")
    board = service.board_from_game(game)
    move, chat = opponent.parse_manual_reply(board, text)
    if move is None:
        # The "second message": give the player a corrective prompt to re-send.
        retry = opponent.build_manual_retry_prompt(game, board, text)
        return jsonify(error="ai.illegal_move", retry_prompt=retry), 400

    flags, board = service.apply_move(game, move.uci())
    opponent.persist_ai_chat(game, chat)
    db.session.commit()
    payload = service.state_payload(game, board=board)
    payload["flags"] = {k: v for k, v in flags.items() if k != "san"}
    payload["ai_chat"] = chat
    payload["chat"] = [m.payload() for m in game.messages.limit(200)]
    payload["my_color"] = game.color_of(current_user.id)
    return jsonify(payload)


# -------------------------------------------------------------------- review
@api_bp.get("/engine/status")
@login_required
def engine_status():
    return jsonify(review.engine_status())


@api_bp.post("/games/<int:game_id>/review/start")
@login_required
def review_start(game_id: int):
    game = _get_game_or_404(game_id)
    if game.result == "*":
        return jsonify(error="game_not_finished"), 400
    speed = request.get_json(silent=True) or {}
    speed_key = speed.get("speed", "normal")
    if speed_key not in VALID_SPEEDS:
        speed_key = "normal"
    result = review.start_review(current_app_(), game, speed_key)
    return jsonify(result)


@api_bp.get("/review/status/<job_id>")
@login_required
def review_status(job_id: str):
    status = review.job_status(job_id)
    if status is None:
        return jsonify(error="no_job"), 404
    return jsonify(status)


@api_bp.get("/games/<int:game_id>/analysis")
@login_required
def game_analysis(game_id: int):
    game = _get_game_or_404(game_id, players_only=False)
    if not game.is_player(current_user.id):
        abort(403)
    if not game.analysis_json:
        return jsonify(analysis=None)
    return jsonify(analysis=_json.loads(game.analysis_json))


# -------------------------------------------------------------------- helpers
def current_app_():
    from flask import current_app
    return current_app._get_current_object()
