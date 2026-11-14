"""Prompt construction and reply parsing for the AI opponent.

The prompt is always written in English (best instruction-following across
models); only the final directive tells the model which spoken language the
player wants, based on the account locale.
"""
from __future__ import annotations

import re

import chess

from ..games.service import ascii_board

REPLY_FORMAT = (
    "Reply in EXACTLY this format, no extra text before or after:\n"
    "MOVE: <one move in UCI notation, e.g. e2e4, taken from the legal moves list>\n"
    "CHAT: <your short in-character message to the player, max 2 sentences>"
)

PERSONAS = {
    "coach": (
        "Friendly Coach",
        "You are a warm, encouraging chess coach. You praise good moves, gently "
        "point out mistakes and love teaching. Keep it light and positive.",
    ),
    "gm": (
        "The Grandmaster",
        "You are a stoic old grandmaster. You speak concisely, with dry wit and "
        "gravity. You respect sharp play and dismiss careless moves.",
    ),
    "trash": (
        "The Trash Talker",
        "You are a cheeky, arrogant trash-talking rival. You mock weak moves, "
        "gloat when ahead and never get genuinely mean — it is playful banter.",
    ),
    "custom": ("Custom persona", ""),
}

LANGUAGE_DIRECTIVE = {
    "en": "Speak to the player in English.",
    "ru": "Speak to the player in Russian ( Russian text ).",
}


def persona_for(key: str, custom: str) -> tuple[str, str]:
    """Returns (name, description); description is '' for the plain AI."""
    if key == "custom" and custom.strip():
        return "Custom opponent", custom.strip()
    if not key or key not in PERSONAS:
        return "Chess AI", ""
    return PERSONAS[key]


def legal_moves_text(board: chess.Board) -> str:
    uci = ", ".join(m.uci() for m in board.legal_moves)
    san = ", ".join(board.san(m) for m in board.legal_moves)
    return f"UCI: {uci}\nSAN: {san}"


def build_prompt(board: chess.Board, *, ai_color: str, username: str,
                 san_history: list[str], last_move_san: str | None,
                 player_message: str | None, lang: str,
                 persona_key: str, persona_custom: str) -> str:
    persona_name, persona_desc = persona_for(persona_key, persona_custom)
    if persona_desc:
        intro = (f"You are {persona_name}: {persona_desc}\n"
                 f"You are playing a friendly game of chess as {ai_color.capitalize()} "
                 f"against a human player named {username}.\n"
                 "You love chess and enjoy chatting between moves.")
    else:
        intro = (f"You are a chess-playing AI in a friendly game of chess as "
                 f"{ai_color.capitalize()} against a human player named {username}.")
    history = " ".join(san_history) or "none yet — this is the first move"
    last = last_move_san or "none yet — the game just started"
    message = (player_message or "").strip()
    if message:
        message_block = f'The player says to you: "{message[:500]}"'
    else:
        message_block = "The player did not send a message this turn."

    return f"""{intro}

--- CURRENT POSITION ---
FEN: {board.fen()}
Board (uppercase = White pieces, lowercase = Black pieces, a8 is top-left):
{ascii_board(board)}
It is your turn to move as {ai_color}.

--- GAME SO FAR ---
Moves so far (SAN): {history}
Opponent's last move: {last}

--- MESSAGES ---
{message_block}

--- LEGAL MOVES (choose strictly from this list) ---
{legal_moves_text(board)}

--- YOUR TASK ---
1. Choose ONE move from the legal moves list above and write it in UCI notation.
2. Write a short in-character comment to the player (max 2 sentences).
{LANGUAGE_DIRECTIVE.get(lang, LANGUAGE_DIRECTIVE['en'])}
{REPLY_FORMAT}"""


def build_retry_prompt(board: chess.Board, *, bad_reply: str, lang: str,
                       persona_key: str, persona_custom: str) -> str:
    """The follow-up message sent when the model produced an illegal move."""
    persona_name, _ = persona_for(persona_key, persona_custom)
    return f"""Your previous answer was:

{bad_reply[:400]}

But that move is ILLEGAL in the current position. This happens sometimes — do not worry.
Pick strictly ONE move from the legal moves list below and answer again in the same format.

--- CURRENT POSITION ---
FEN: {board.fen()}
Board (uppercase = White, lowercase = Black):
{ascii_board(board)}

--- LEGAL MOVES (choose strictly from this list) ---
{legal_moves_text(board)}

{LANGUAGE_DIRECTIVE.get(lang, LANGUAGE_DIRECTIVE['en'])}
{REPLY_FORMAT}"""


def parse_reply(text: str) -> tuple[str | None, str | None]:
    """Extract (move_token, chat) from a model reply.

    Returns (None, None) when nothing sensible could be parsed at all.
    """
    if not text:
        return None, None
    move = chat = None
    match = re.search(r"MOVE:\s*([^\n\r]+)", text, re.IGNORECASE)
    if match:
        move = match.group(1).strip().strip("`\"' *")
    match = re.search(r"CHAT:\s*(.+)", text, re.IGNORECASE | re.DOTALL)
    if match:
        chat = match.group(1).strip().strip("`\"'")
        chat = re.sub(r"\s*\n\s*", " ", chat)[:500]
    return move, chat


def resolve_move(board: chess.Board, token: str | None) -> chess.Move | None:
    """Interpret a move token as UCI first, then as SAN; must be legal."""
    if not token:
        return None
    token = token.strip().lower()
    try:
        move = chess.Move.from_uci(token)
        if move in board.legal_moves:
            return move
    except ValueError:
        pass
    try:
        return board.parse_san(token.replace("0", "O"))
    except (ValueError, chess.InvalidMoveError):
        return None
