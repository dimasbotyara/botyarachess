"""AI opponent driver: turns a model's words into a legal move.

Flow per AI turn:
1. Build the English prompt (position + last move + player chat message).
2. Ask the provider; parse MOVE/CHAT; validate the move with python-chess.
3. On an illegal move send the corrective retry prompt (up to 3 attempts).
4. Still failing -> apologise (localized key) and play a random legal move,
   so the game never gets stuck because a model had a bad day.
"""
from __future__ import annotations

import chess

from ..extensions import db
from ..localization.strings import locale_for
from ..models import ChatMessage, Game, User
from ..games.service import random_legal_uci
from . import providers
from .prompts import build_prompt, build_retry_prompt, parse_reply, resolve_move

AI_MAX_ATTEMPTS = 3


class AIResult:
    """Outcome of one AI turn, ready for the caller to apply."""

    def __init__(self) -> None:
        self.move: chess.Move | None = None      # always set unless game over
        self.chat: str | None = None             # model text or i18n key
        self.chat_kind: str = "text"             # "text" | "key"
        self.used_fallback: bool = False
        self.attempts: int = 0
        self.error_key: str | None = None


def _ai_user(game: Game) -> User | None:
    return game.white if game.ai_side == "black" else game.black


def persist_ai_chat(game: Game, chat: str | None, kind: str = "text") -> None:
    if chat:
        db.session.add(ChatMessage(game_id=game.id, sender="ai", text=chat, kind=kind))
        db.session.commit()


def persist_player_chat(game: Game, text: str) -> None:
    db.session.add(ChatMessage(game_id=game.id, sender="player", text=text[:500]))
    db.session.commit()


def make_ai_move(game: Game, board: chess.Board, player_message: str | None) -> AIResult:
    """Run one full AI turn for `game` at position `board` (AI to move)."""
    result = AIResult()
    user = _ai_user(game)
    lang = locale_for(user)
    cfg = user.ai if user else {}
    ai_color = game.ai_side or "black"

    prompt = build_prompt(
        board,
        ai_color=ai_color,
        username=user.username if user else "Player",
        san_history=game.san_list[:-1] if game.san_list else [],
        last_move_san=game.san_list[-1] if game.san_list else None,
        player_message=player_message,
        lang=lang,
        persona_key=cfg.get("persona") or "coach",
        persona_custom=cfg.get("persona_custom") or "",
    )

    for attempt in range(1, AI_MAX_ATTEMPTS + 1):
        result.attempts = attempt
        try:
            raw = providers.call_llm(cfg, prompt, prompt)
        except providers.AIProviderError as exc:
            result.error_key = "ai.provider_error"
            result.chat_kind = "key"
            result.chat = f"ai.provider_error|{exc}"
            break

        move_token, chat = parse_reply(raw)
        move = resolve_move(board, move_token)
        if move is not None:
            result.move = move
            result.chat = chat
            break

        # Illegal or missing move -> corrective follow-up (the "second message").
        result.error_key = "ai.illegal_move"
        prompt = build_retry_prompt(
            board, bad_reply=raw or "(empty reply)", lang=lang,
            persona_key=cfg.get("persona") or "coach",
            persona_custom=cfg.get("persona_custom") or "",
        )

    if result.move is None:
        # All attempts failed: apologize and keep the game going.
        result.used_fallback = True
        result.chat_kind = "key"
        if result.chat is None:
            result.chat = "ai.fallback_random"
        uci = random_legal_uci(board)
        result.move = chess.Move.from_uci(uci) if uci else None
    return result


def last_player_message(game: Game) -> str | None:
    msg = (game.messages.filter_by(sender="player")
           .order_by(ChatMessage.id.desc()).first())
    return msg.text if msg else None


def build_manual_prompt(game: Game, board: chess.Board) -> str:
    """Prompt shown to the player for copy-pasting into any external chatbot."""
    user = _ai_user(game)
    lang = locale_for(user) if user else "en"
    cfg = user.ai if user else {}
    return build_prompt(
        board,
        ai_color=game.ai_side or "black",
        username=user.username if user else "Player",
        san_history=game.san_list[:-1] if game.san_list else [],
        last_move_san=game.san_list[-1] if game.san_list else None,
        player_message=last_player_message(game),
        lang=lang,
        persona_key=cfg.get("persona") or "coach",
        persona_custom=cfg.get("persona_custom") or "",
    )


def parse_manual_reply(board: chess.Board, text: str) -> tuple[chess.Move | None,
                                                               str | None]:
    """Parse a pasted model reply for the manual mode."""
    move_token, chat = parse_reply(text)
    move = resolve_move(board, move_token)
    return move, chat


def build_manual_retry_prompt(game: Game, board: chess.Board, bad_text: str) -> str:
    """Corrective prompt (the "second message") for the manual mode."""
    user = _ai_user(game)
    lang = locale_for(user) if user else "en"
    cfg = user.ai if user else {}
    return build_retry_prompt(
        board, bad_reply=bad_text or "(empty reply)", lang=lang,
        persona_key=cfg.get("persona") or "coach",
        persona_custom=cfg.get("persona_custom") or "",
    )
