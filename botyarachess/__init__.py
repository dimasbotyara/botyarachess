"""botyarachess — offline-first chess web application.

Flask + python-chess backend with SocketIO-powered online play,
LLM-driven AI opponents and a fully local (no-CDN) frontend.
"""
from __future__ import annotations

from flask import Flask, render_template
from flask_login import current_user

from .config import Config
from .extensions import csrf, db, login_manager, socketio
from .localization.strings import locale_for


def create_app(config_object: type[Config] = Config) -> Flask:
    app = Flask(__name__, static_folder="../static", template_folder="../templates")
    app.config.from_object(config_object)

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    socketio.init_app(app)

    from .models import User

    @login_manager.user_loader
    def load_user(user_id: str):
        return db.session.get(User, int(user_id))

    # ---------------------------------------------------------------- routes
    from .routes import api, auth, main, play

    app.register_blueprint(auth.auth_bp)
    app.register_blueprint(main.main_bp)
    app.register_blueprint(play.play_bp)
    app.register_blueprint(api.api_bp)

    # ------------------------------------------------------- template globals
    @app.context_processor
    def inject_globals():
        user = current_user if current_user.is_authenticated else None
        return {
            "current_theme": user.theme if user else None,
            "current_locale": locale_for(user),
            "current_username": user.username if user else None,
        }

    @app.errorhandler(404)
    def not_found(_error):
        return render_template("errors/404.html"), 404

    @app.errorhandler(403)
    def forbidden(_error):
        return render_template("errors/403.html"), 403

    with app.app_context():
        db.create_all()

    from .games.events import start_flag_watcher
    start_flag_watcher()

    return app
