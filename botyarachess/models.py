"""Database models: users, games and in-game chat messages."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


DEFAULT_SETTINGS = {
    "sounds": True,
    "coords": True,
    "animations": True,
    "highlight_legal": True,
    "accent": "",              # accent id from the current theme's palette
    "board_theme": "auto",     # auto = follow the site theme
    "font_size": "normal",     # small | normal | large
    "reduce_motion": False,
    "board_size": "normal",    # small | normal | large
    "show_captured": True,
    "volume": 70,              # 0..100
    "autoflip": False,
}

DEFAULT_AI = {
    "provider": "manual",   # manual | openai | anthropic | gemini | lmstudio | compat
    "model": "",
    "api_key": "",
    "base_url": "",         # for the generic OpenAI-compatible provider
    "lm_host": "",          # LM Studio: hostname or IP (no scheme/port)
    "lm_port": 1234,
    "persona": "coach",     # coach | gm | trash | custom
    "persona_custom": "",
    "chat_enabled": True,
    "temperature": 0.7,
}


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(32), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)

    # preferences (persisted so they follow the account across devices)
    theme = db.Column(db.String(32), default="catppuccin-mocha", nullable=False)
    locale = db.Column(db.String(8), default="", nullable=False)  # "" = auto-detect
    settings_json = db.Column(db.Text, default="{}", nullable=False)
    ai_json = db.Column(db.Text, default="{}", nullable=False)

    # online play
    rating = db.Column(db.Integer, default=1200, nullable=False)
    wins = db.Column(db.Integer, default=0, nullable=False)
    losses = db.Column(db.Integer, default=0, nullable=False)
    draws = db.Column(db.Integer, default=0, nullable=False)

    games = db.relationship("Game", lazy="dynamic", foreign_keys="Game.white_id")

    # ------------------------------------------------------------------ auth
    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    # -------------------------------------------------------------- settings
    @property
    def settings(self) -> dict:
        data = dict(DEFAULT_SETTINGS)
        try:
            data.update(json.loads(self.settings_json or "{}"))
        except (ValueError, TypeError):
            pass
        return data

    def update_settings(self, patch: dict) -> None:
        """Type-aware patch of the settings JSON (booleans stay bools, etc.)."""
        data = self.settings
        for key, default in DEFAULT_SETTINGS.items():
            if key not in patch:
                continue
            value = patch[key]
            if isinstance(default, bool):
                data[key] = bool(value)
            elif isinstance(default, int) and not isinstance(default, bool):
                try:
                    data[key] = max(0, min(100, int(value)))
                except (TypeError, ValueError):
                    continue
            else:
                data[key] = str(value)[:40]
        self.settings_json = json.dumps(data)

    @property
    def ai(self) -> dict:
        data = dict(DEFAULT_AI)
        try:
            data.update(json.loads(self.ai_json or "{}"))
        except (ValueError, TypeError):
            pass
        return data

    def update_ai(self, patch: dict) -> dict:
        data = self.ai
        for key in DEFAULT_AI:
            if key in patch:
                value = patch[key]
                data[key] = value
        self.ai_json = json.dumps(data)
        return data

    def masked_ai(self) -> dict:
        """AI config safe to send to the client: the API key is never returned."""
        data = self.ai
        key = data.get("api_key") or ""
        masked = ("••••" + key[-4:]) if len(key) >= 4 else ("••••" if key else "")
        out = dict(data)
        out["api_key_set"] = bool(key)
        out["api_key_masked"] = masked
        out.pop("api_key", None)
        return out

    @property
    def total_games(self) -> int:
        return self.wins + self.losses + self.draws

    def record(self, result: str, my_color: str) -> None:
        """Update win/loss/draw counters after a finished game."""
        if result == "1/2-1/2":
            self.draws += 1
        elif (result == "1-0") == (my_color == "white"):
            self.wins += 1
        else:
            self.losses += 1

    def public(self) -> dict:
        return {
            "id": self.id,
            "username": self.username,
            "rating": self.rating,
            "wins": self.wins,
            "losses": self.losses,
            "draws": self.draws,
        }

    def __repr__(self) -> str:  # pragma: no cover
        return f"<User {self.username}>"


class Game(db.Model):
    __tablename__ = "games"

    id = db.Column(db.Integer, primary_key=True)
    mode = db.Column(db.String(16), nullable=False)  # hotseat | online | ai

    white_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    black_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    white = db.relationship("User", foreign_keys=[white_id])
    black = db.relationship("User", foreign_keys=[black_id])

    ai_side = db.Column(db.String(8), default="", nullable=False)  # "" | white | black
    ai_provider = db.Column(db.String(24), default="", nullable=False)
    ai_model = db.Column(db.String(120), default="", nullable=False)

    result = db.Column(db.String(8), default="*", nullable=False)  # 1-0 | 0-1 | 1/2-1/2 | *
    termination = db.Column(db.String(24), default="", nullable=False)
    # checkmate | stalemate | resign | timeout | agreement | insufficient |
    # fifty-move | threefold | abandoned

    time_control = db.Column(db.String(12), default="none", nullable=False)
    rated = db.Column(db.Boolean, default=False, nullable=False)

    moves_uci = db.Column(db.Text, default="", nullable=False)
    moves_san = db.Column(db.Text, default="", nullable=False)

    analysis_json = db.Column(db.Text, default="", nullable=False)

    started_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    finished_at = db.Column(db.DateTime(timezone=True), nullable=True)

    messages = db.relationship(
        "ChatMessage", backref="game", lazy="dynamic",
        cascade="all, delete-orphan", order_by="ChatMessage.id",
    )

    # ------------------------------------------------------------- utilities
    @property
    def uci_list(self) -> list[str]:
        return self.moves_uci.split() if self.moves_uci else []

    @property
    def san_list(self) -> list[str]:
        return self.moves_san.split() if self.moves_san else []

    def player_id_for(self, color: str) -> int | None:
        return self.white_id if color == "white" else self.black_id

    def color_of(self, user_id: int) -> str | None:
        if user_id is None:
            return None
        if self.white_id == user_id:
            return "white"
        if self.black_id == user_id:
            return "black"
        return None

    def is_player(self, user_id: int) -> bool:
        return self.color_of(user_id) is not None

    def is_active(self) -> bool:
        return self.result == "*"

    def human_side(self) -> str | None:
        """For AI games: the color the human plays."""
        if self.mode != "ai":
            return None
        if self.ai_side == "white":
            return "black"
        if self.ai_side == "black":
            return "white"
        return "white"

    def winner_color(self) -> str | None:
        if self.result == "1-0":
            return "white"
        if self.result == "0-1":
            return "black"
        return None

    def players_payload(self) -> dict:
        def info(user: User | None) -> dict:
            if user is None:
                return {"id": None, "username": "", "rating": None}
            return user.public()
        return {"white": info(self.white), "black": info(self.black)}


class ChatMessage(db.Model):
    __tablename__ = "chat_messages"

    id = db.Column(db.Integer, primary_key=True)
    game_id = db.Column(db.Integer, db.ForeignKey("games.id"), nullable=False, index=True)
    sender = db.Column(db.String(16), nullable=False)  # player | ai | system
    kind = db.Column(db.String(8), default="text", nullable=False)  # text | key
    text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)

    def payload(self) -> dict:
        return {
            "id": self.id,
            "sender": self.sender,
            "kind": self.kind,
            "text": self.text,
            "ts": self.created_at.isoformat() if self.created_at else None,
        }
