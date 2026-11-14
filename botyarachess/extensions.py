"""Shared Flask extension instances (created here, bound to the app in create_app)."""
from __future__ import annotations

from flask_login import LoginManager
from flask_socketio import SocketIO
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect

db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()

# threading keeps us dependency-free (no eventlet/gevent) and is fine for a
# LAN-scale app; every request runs in its own worker thread.
socketio = SocketIO(
    async_mode="threading",
    cors_allowed_origins=[],
    logger=False,
    engineio_logger=False,
)

login_manager.login_view = "auth.login"
login_manager.login_message_category = "warning"
