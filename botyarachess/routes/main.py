"""Main pages: dashboard, profile, settings, game history, review view."""
from __future__ import annotations

from flask import Blueprint, abort, render_template
from flask_login import current_user, login_required

from ..engine import review
from ..models import Game

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
@login_required
def index():
    recent = (Game.query
              .filter((Game.white_id == current_user.id) |
                      (Game.black_id == current_user.id))
              .order_by(Game.started_at.desc())
              .limit(5).all())
    return render_template("index.html", recent=recent)


@main_bp.route("/profile")
@login_required
def profile():
    games = (Game.query
             .filter((Game.white_id == current_user.id) |
                     (Game.black_id == current_user.id),
                     Game.result != "*")
             .order_by(Game.started_at.desc())
             .limit(50).all())
    return render_template("profile.html", games=games, engine=review.engine_status())


@main_bp.route("/settings")
@login_required
def settings():
    return render_template("settings.html", engine=review.engine_status())


@main_bp.route("/games")
@login_required
def games():
    items = (Game.query
             .filter((Game.white_id == current_user.id) |
                     (Game.black_id == current_user.id),
                     Game.result != "*")
             .order_by(Game.started_at.desc())
             .limit(100).all())
    return render_template("games.html", games=items)


@main_bp.route("/review/<int:game_id>")
@login_required
def review_page(game_id: int):
    import json

    game = db_get_game(game_id)
    if game is None or not game.is_player(current_user.id):
        abort(404)
    if game.result == "*":
        abort(400)

    review_data = {
        "id": game.id,
        "moves": game.san_list,
        "players": {
            "white": game.white.username if game.white else "AI",
            "black": game.black.username if game.black else "AI",
        },
    }
    return render_template(
        "review.html",
        game=game,
        engine=review.engine_status(),
        review_data_json=json.dumps(review_data, ensure_ascii=False),
    )


# helpers kept tiny to avoid an extra import block at the top
def db_get_game(game_id: int):
    from ..extensions import db
    return db.session.get(Game, game_id)
