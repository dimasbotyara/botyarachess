"""Online play manager: matchmaking queue, open challenges and live rooms.

Pure in-memory state (rooms only exist while players are connected); the
game itself lives in the database and sockets just drive it.
"""
from __future__ import annotations

import secrets
import string
import threading
import time
from dataclasses import dataclass, field

import chess

from ..games.service import TIME_CONTROLS

CODE_ALPHABET = string.ascii_uppercase + string.digits
GRACE_SECONDS = 20  # reconnect window before a disconnect counts as abandoning


def new_code() -> str:
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(6))


@dataclass
class TimeControl:
    initial: int   # seconds
    increment: int  # seconds per move


@dataclass
class Seat:
    user_id: int
    username: str
    rating: int
    sid: str | None = None


@dataclass
class Room:
    game_id: int
    code: str
    tc_key: str
    rated: bool
    white: Seat
    black: Seat
    board: chess.Board = field(default_factory=chess.Board)
    spectators: set = field(default_factory=set)
    white_ms: int = 0
    black_ms: int = 0
    last_tick: float | None = None   # monotonic time of the last clock update
    draw_offered_by: str | None = None
    rematch_offered_by: int | None = None
    finished: bool = False
    stop_event: threading.Event = field(default_factory=threading.Event)

    def seat_for(self, user_id: int) -> Seat | None:
        if self.white.user_id == user_id:
            return self.white
        if self.black.user_id == user_id:
            return self.black
        return None

    def color_for(self, user_id: int) -> str | None:
        if self.white.user_id == user_id:
            return "white"
        if self.black.user_id == user_id:
            return "black"
        return None

    def active_clock(self) -> tuple[str, int] | None:
        """(color, remaining_ms) of the side that is burning time right now."""
        if self.finished or self.last_tick is None or self.board.is_game_over():
            return None
        color = "white" if self.board.turn == chess.WHITE else "black"
        elapsed_ms = int((time.monotonic() - self.last_tick) * 1000)
        remaining = max(0, (self.white_ms if color == "white" else self.black_ms) - elapsed_ms)
        return color, remaining


@dataclass
class Challenge:
    code: str
    user_id: int
    username: str
    rating: int
    tc_key: str
    rated: bool


@dataclass
class QueueEntry:
    sid: str
    user_id: int
    username: str
    rating: int
    tc_key: str
    rated: bool


class Lobby:
    """All matchmaking state, guarded by one re-entrant lock."""

    def __init__(self) -> None:
        self.lock = threading.RLock()
        self.challenges: dict[str, Challenge] = {}
        self.queues: dict[str, list[QueueEntry]] = {}
        self.rooms: dict[int, Room] = {}

    # ----------------------------------------------------------- challenges
    def create_challenge(self, user, tc_key: str, rated: bool) -> Challenge:
        with self.lock:
            challenge = Challenge(
                code=new_code(),
                user_id=user.id,
                username=user.username,
                rating=user.rating,
                tc_key=tc_key,
                rated=rated,
            )
            self.challenges[challenge.code] = challenge
            return challenge

    def cancel_challenge(self, user_id: int) -> None:
        with self.lock:
            for code, challenge in list(self.challenges.items()):
                if challenge.user_id == user_id:
                    del self.challenges[code]

    def take_challenge(self, code: str) -> Challenge | None:
        with self.lock:
            return self.challenges.pop(code, None)

    # ------------------------------------------------------------ quick match
    def queue_add(self, entry: QueueEntry) -> QueueEntry | None:
        """Add the player to a queue; returns an opponent if one was waiting."""
        with self.lock:
            bucket = self.queues.setdefault(entry.tc_key, [])
            # same user might double-click; drop stale duplicates
            bucket[:] = [e for e in bucket if e.user_id != entry.user_id]
            if bucket:
                opponent = bucket.pop(0)
                return opponent
            bucket.append(entry)
            return None

    def queue_remove(self, sid: str) -> None:
        with self.lock:
            for bucket in self.queues.values():
                bucket[:] = [e for e in bucket if e.sid != sid]

    # ------------------------------------------------------------------ rooms
    def create_room(self, game_id: int, tc_key: str, rated: bool,
                    white_user, black_user, start_clocks: bool) -> Room:
        tc = TIME_CONTROLS[tc_key]
        initial, increment = tc if tc else (0, 0)
        room = Room(
            game_id=game_id,
            code=new_code(),
            tc_key=tc_key,
            rated=rated,
            white=Seat(white_user.id, white_user.username, white_user.rating),
            black=Seat(black_user.id, black_user.username, black_user.rating),
            white_ms=initial * 1000,
            black_ms=initial * 1000,
        )
        with self.lock:
            self.rooms[game_id] = room
        return room

    def get_room(self, game_id: int) -> Room | None:
        with self.lock:
            return self.rooms.get(game_id)

    def drop_room(self, game_id: int) -> None:
        with self.lock:
            room = self.rooms.pop(game_id, None)
        if room:
            room.stop_event.set()

    def challenges_payload(self) -> list[dict]:
        with self.lock:
            return [
                {
                    "code": c.code, "user_id": c.user_id,
                    "username": c.username, "rating": c.rating,
                    "tc": c.tc_key, "rated": c.rated,
                }
                for c in self.challenges.values()
            ]


LOBBY = Lobby()


# ---------------------------------------------------------------------- clocks
def apply_move_clock(room: Room, mover_color: str) -> None:
    """Deduct elapsed time from the mover and add the increment."""
    if room.tc_key == "none":
        return
    now = time.monotonic()
    if room.last_tick is not None:
        elapsed_ms = int((now - room.last_tick) * 1000)
        tc = TIME_CONTROLS[room.tc_key]
        increment_ms = tc[1] * 1000
        if mover_color == "white":
            room.white_ms = max(0, room.white_ms - elapsed_ms + increment_ms)
        else:
            room.black_ms = max(0, room.black_ms - elapsed_ms + increment_ms)
    room.last_tick = now


def clocks_payload(room: Room) -> dict | None:
    if room.tc_key == "none":
        return None
    active = room.active_clock()
    return {
        "white": room.white_ms,
        "black": room.black_ms,
        "running": active[0] if active else None,
        "server_ts": time.time(),
    }
