"""Play pages: AI setup, online lobby, the unified game page."""
from __future__ import annotations

from flask import Blueprint, abort, redirect, render_template, url_for
from flask_login import current_user, login_required

from ..ai.providers import DEFAULT_MODELS, PROVIDER_LABELS, PROVIDERS
from ..models import Game

play_bp = Blueprint("play", __name__)


@play_bp.route("/play/hotseat")
@login_required
def play_hotseat():
    """One click = a fresh hotseat game."""
    from ..extensions import db

    game = Game(mode="hotseat", white_id=current_user.id, black_id=current_user.id)
    db.session.add(game)
    db.session.commit()
    return redirect(url_for("play.game_page", game_id=game.id))


@play_bp.route("/play/ai")
@login_required
def play_ai():
    return render_template("play/ai.html",
                           providers=PROVIDERS,
                           provider_labels=PROVIDER_LABELS,
                           default_models=DEFAULT_MODELS)


@play_bp.route("/play/online")
@login_required
def play_online():
    return render_template("play/online.html")


@play_bp.route("/game/<int:game_id>")
@login_required
def game_page(game_id: int):
    import json

    from ..extensions import db
    from ..games import service

    game = db.session.get(Game, game_id)
    if game is None:
        abort(404)
    is_player = game.is_player(current_user.id)
    # hotseat/ai games are private to their creator; online games allow spectating
    if not is_player and game.mode != "online":
        abort(403)

    state = service.state_payload(game)
    if game.mode == "ai":
        state["chat"] = [m.payload() for m in game.messages.limit(200)]
        state["ai"] = current_user.masked_ai()

    return render_template(
        "play/game.html",
        game=game,
        is_player=is_player,
        my_color=game.color_of(current_user.id),
        game_state_json=json.dumps(state, ensure_ascii=False),
    )
