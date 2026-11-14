"""SocketIO event handlers for online play.

Client events:  lobby:state, challenge:create/cancel/join, quick:join/cancel,
                game:join, game:move, game:chat, game:resign,
                game:draw:offer/accept/decline, game:rematch
Server events:  lobby:state, queue:waiting/cancelled, game:started,
                game:state, game:move, game:over, game:chat,
                game:draw:*, player:disconnected
"""
from __future__ import annotations

import random
import threading
import time

import chess
from flask import request
from flask_login import current_user
from flask_socketio import disconnect, emit, join_room, leave_room

from ..extensions import db, socketio
from ..models import ChatMessage, Game, User, utcnow
from . import manager, service

ROOM_PREFIX = "game:"
SID_USER: dict[str, dict] = {}
_SID_LOCK = threading.Lock()

_flag_thread_started = False


def game_room(game_id: int) -> str:
    return f"{ROOM_PREFIX}{game_id}"


def _broadcast_lobby() -> None:
    socketio.emit("lobby:state", {"challenges": LOBBY_PAYLOAD()})


def LOBBY_PAYLOAD() -> list[dict]:
    return manager.LOBBY.challenges_payload()


def _persist(game: Game) -> None:
    db.session.add(game)
    db.session.commit()


# ------------------------------------------------------------------ lifecycle
@socketio.on("connect")
def on_connect():
    if not current_user.is_authenticated:
        disconnect()
        return False
    with _SID_LOCK:
        SID_USER[request.sid] = {
            "user_id": current_user.id,
            "username": current_user.username,
        }
    emit("lobby:state", {"challenges": LOBBY_PAYLOAD()})


@socketio.on("disconnect")
def on_disconnect():
    with _SID_LOCK:
        info = SID_USER.pop(request.sid, None)
    if not info:
        return
    manager.LOBBY.queue_remove(request.sid)
    manager.LOBBY.cancel_challenge(info["user_id"])
    _broadcast_lobby()
    _handle_seat_drop(info["user_id"], request.sid)


def _handle_seat_drop(user_id: int, sid: str) -> None:
    """Mark the seat offline and schedule a forfeit if they stay gone."""
    room = None
    for candidate in list(manager.LOBBY.rooms.values()):
        seat = candidate.seat_for(user_id)
        if seat is not None and seat.sid == sid and not candidate.finished:
            room = candidate
            break
    if room is None:
        return

    color = room.color_for(user_id)
    socketio.emit(
        "player:disconnected",
        {"color": color, "grace": manager.GRACE_SECONDS},
        to=game_room(room.game_id),
    )

    seat = room.seat_for(user_id)
    seat.sid = None

    def forfeit_if_gone():
        time.sleep(manager.GRACE_SECONDS)
        if seat.sid is None and not room.finished:
            _finish(room, room.color_for(user_id), "abandoned")

    threading.Thread(target=forfeit_if_gone, daemon=True).start()


# ---------------------------------------------------------------------- lobby
@socketio.on("lobby:state")
def on_lobby_state():
    emit("lobby:state", {"challenges": LOBBY_PAYLOAD()})


@socketio.on("challenge:create")
def on_challenge_create(data):
    tc_key = data.get("tc", "5+0")
    if tc_key not in service.TIME_CONTROLS:
        tc_key = "5+0"
    rated = bool(data.get("rated", False))
    manager.LOBBY.cancel_challenge(current_user.id)
    challenge = manager.LOBBY.create_challenge(current_user, tc_key, rated)
    _broadcast_lobby()
    emit("challenge:created", {"code": challenge.code})


@socketio.on("challenge:cancel")
def on_challenge_cancel(_data=None):
    manager.LOBBY.cancel_challenge(current_user.id)
    _broadcast_lobby()
    emit("challenge:cancelled")


@socketio.on("challenge:join")
def on_challenge_join(data):
    code = str(data.get("code") or "").upper()
    challenge = manager.LOBBY.take_challenge(code)
    if challenge is None:
        emit("error:toast", {"key": "lobby.challenge_gone"})
        return
    opponent = db.session.get(User, challenge.user_id)
    if opponent is None or opponent.id == current_user.id:
        emit("error:toast", {"key": "lobby.challenge_gone"})
        return
    _broadcast_lobby()
    _start_game(white_user=opponent, black_user=current_user,
                tc_key=challenge.tc_key, rated=challenge.rated)


@socketio.on("quick:join")
def on_quick_join(data):
    tc_key = data.get("tc", "5+0")
    if tc_key not in service.TIME_CONTROLS or tc_key == "none":
        tc_key = "5+0"
    rated = bool(data.get("rated", True))
    entry = manager.QueueEntry(
        sid=request.sid,
        user_id=current_user.id,
        username=current_user.username,
        rating=current_user.rating,
        tc_key=tc_key,
        rated=rated,
    )
    opponent = manager.LOBBY.queue_add(entry)
    if opponent is None:
        emit("queue:waiting", {"tc": tc_key})
        return

    opponent_user = db.session.get(User, opponent.user_id)
    if opponent_user is None:
        emit("error:toast", {"key": "lobby.opponent_gone"})
        return
    # The winner of the coin toss gets white.
    me_white = random.random() < 0.5
    white_user = current_user if me_white else opponent_user
    black_user = opponent_user if me_white else current_user
    socketio.emit("queue:matched", {}, to=opponent.sid)
    _start_game(white_user=white_user, black_user=black_user,
                tc_key=tc_key, rated=rated)


@socketio.on("quick:cancel")
def on_quick_cancel(_data=None):
    manager.LOBBY.queue_remove(request.sid)
    emit("queue:cancelled")


# ----------------------------------------------------------------- game start
def _start_game(white_user: User, black_user: User, tc_key: str, rated: bool) -> None:
    game = Game(
        mode="online",
        white_id=white_user.id,
        black_id=black_user.id,
        time_control=tc_key,
        rated=rated,
    )
    db.session.add(game)
    db.session.commit()

    room = manager.LOBBY.create_room(game.id, tc_key, rated, white_user, black_user,
                                     start_clocks=True)
    payload = {
        "game_id": game.id,
        "white": white_user.public(),
        "black": black_user.public(),
        "tc": tc_key,
        "rated": rated,
    }

    # Join both players into the socket room by their current sids.
    with _SID_LOCK:
        for sid, info in SID_USER.items():
            if info["user_id"] in (white_user.id, black_user.id):
                join_room(game_room(game.id), sid=sid)
                if info["user_id"] == white_user.id:
                    room.white.sid = sid
                else:
                    room.black.sid = sid

    socketio.emit("game:started", payload, to=game_room(game.id))
    if room.tc_key != "none":
        room.last_tick = time.monotonic()


@socketio.on("game:join")
def on_game_join(data):
    game_id = int(data.get("game_id") or 0)
    game = db.session.get(Game, game_id)
    if game is None:
        emit("error:toast", {"key": "game.not_found"})
        return
    join_room(game_room(game_id))
    room = manager.LOBBY.get_room(game_id)
    if room is not None:
        seat = room.seat_for(current_user.id)
        if seat is not None:
            was_reconnect = seat.sid is None
            seat.sid = request.sid
            if was_reconnect:
                socketio.emit("player:reconnected",
                              {"color": room.color_for(current_user.id)},
                              to=game_room(game_id))
    elif not game.is_player(current_user.id):
        pass  # spectator: fine
    clocks = manager.clocks_payload(room) if room else None
    emit("game:state", service.state_payload(game, clocks=clocks))


# ------------------------------------------------------------------- gameplay
@socketio.on("game:move")
def on_game_move(data):
    game_id = int(data.get("game_id") or 0)
    uci = str(data.get("uci") or "")
    room = manager.LOBBY.get_room(game_id)
    game = db.session.get(Game, game_id)
    if game is None or room is None or room.finished:
        emit("error:toast", {"key": "game.not_found"})
        return

    color = room.color_for(current_user.id)
    if color is None:
        emit("error:toast", {"key": "game.not_player"})
        return
    expected = "white" if room.board.turn == chess.WHITE else "black"
    if color != expected:
        emit("error:toast", {"key": "game.not_your_turn"})
        return

    try:
        flags, board = service.apply_move(game, uci)
    except ValueError as exc:
        emit("error:toast", {"key": f"game.invalid_{exc}"})
        return

    manager.apply_move_clock(room, color)
    room.board = board  # keep the room's position in sync with the game
    db.session.commit()

    payload = service.state_payload(game, board=board,
                                    clocks=manager.clocks_payload(room))
    payload["flags"] = {k: v for k, v in flags.items() if k != "san"}
    payload["san"] = flags["san"]
    socketio.emit("game:move", payload, to=game_room(game_id))

    if flags.get("game_over"):
        _close_room(room, game)


@socketio.on("game:chat")
def on_game_chat(data):
    game_id = int(data.get("game_id") or 0)
    text = str(data.get("text") or "").strip()
    if not text:
        return
    game = db.session.get(Game, game_id)
    room = manager.LOBBY.get_room(game_id)
    if game is None or room is None:
        return
    message = ChatMessage(game_id=game.id, sender="player", text=text[:500])
    db.session.add(message)
    db.session.commit()
    socketio.emit("game:chat",
                  {"username": current_user.username,
                   "user_id": current_user.id,
                   "text": text[:500]},
                  to=game_room(game_id))


@socketio.on("game:resign")
def on_game_resign(data):
    game_id = int(data.get("game_id") or 0)
    room = manager.LOBBY.get_room(game_id)
    game = db.session.get(Game, game_id)
    if game is None or room is None or room.finished:
        return
    color = room.color_for(current_user.id)
    if color is None:
        return
    _finish(room, color, "resign")


# -------------------------------------------------------------------- draws
@socketio.on("game:draw:offer")
def on_draw_offer(data):
    game_id = int(data.get("game_id") or 0)
    room = manager.LOBBY.get_room(game_id)
    if room is None or room.finished:
        return
    color = room.color_for(current_user.id)
    if color is None:
        return
    room.draw_offered_by = color
    socketio.emit("game:draw:offered",
                  {"by": current_user.username, "color": color},
                  to=game_room(game_id))


@socketio.on("game:draw:accept")
def on_draw_accept(data):
    game_id = int(data.get("game_id") or 0)
    room = manager.LOBBY.get_room(game_id)
    if room is None or room.finished or room.draw_offered_by is None:
        return
    color = room.color_for(current_user.id)
    if color is None or color == room.draw_offered_by:
        return
    room.draw_offered_by = None
    _finish(room, None, "agreement")


@socketio.on("game:draw:decline")
def on_draw_decline(data):
    game_id = int(data.get("game_id") or 0)
    room = manager.LOBBY.get_room(game_id)
    if room is None:
        return
    room.draw_offered_by = None
    socketio.emit("game:draw:declined", {}, to=game_room(game_id))


# ------------------------------------------------------------------ rematch
@socketio.on("game:rematch")
def on_rematch(data):
    game_id = int(data.get("game_id") or 0)
    room = manager.LOBBY.get_room(game_id)
    if room is None or not room.finished:
        return
    if room.rematch_offered_by is None:
        room.rematch_offered_by = current_user.id
        socketio.emit("game:rematch:offered",
                      {"username": current_user.username},
                      to=game_room(game_id))
        return
    if room.rematch_offered_by == current_user.id:
        return
    # Both agreed: swap colors and start a fresh game in a new room.
    white_user = db.session.get(User, room.black.user_id)
    black_user = db.session.get(User, room.white.user_id)
    old_room_id = room.game_id
    manager.LOBBY.drop_room(old_room_id)
    _start_game(white_user=white_user, black_user=black_user,
                tc_key=room.tc_key, rated=room.rated)


# ------------------------------------------------------------------- helpers
def _finish(room: manager.Room, loser_color: str | None, termination: str) -> None:
    """Finish a game from the socket side (resign / timeout / abandoned)."""
    if room.finished:
        return
    room.finished = True
    room.stop_event.set()

    game = db.session.get(Game, room.game_id)
    if game is None:
        return
    if loser_color == "white":
        result = "0-1"
    elif loser_color == "black":
        result = "1-0"
    else:
        result = "1/2-1/2"
    service.finish_game(game, result, termination)

    socketio.emit("game:over", {
        "result": result,
        "termination": termination,
        "clocks": manager.clocks_payload(room),
        "state": service.state_payload(game, clocks=manager.clocks_payload(room)),
    }, to=game_room(room.game_id))


def _close_room(room: manager.Room, game: Game) -> None:
    """Called after a move ended the game (mate/stalemate/draw rules)."""
    room.finished = True
    room.stop_event.set()
    socketio.emit("game:over", {
        "result": game.result,
        "termination": game.termination,
        "clocks": manager.clocks_payload(room),
        "state": service.state_payload(game, clocks=manager.clocks_payload(room)),
    }, to=game_room(room.game_id))


def _flag_watcher() -> None:
    """Background loop: flag players who ran out of time."""
    while True:
        time.sleep(0.5)
        for room in list(manager.LOBBY.rooms.values()):
            if room.finished or room.tc_key == "none":
                continue
            active = room.active_clock()
            if active is None:
                continue
            color, remaining = active
            if remaining <= 0:
                _finish(room, color, "timeout")


def start_flag_watcher() -> None:
    global _flag_thread_started
    if not _flag_thread_started:
        _flag_thread_started = True
        threading.Thread(target=_flag_watcher, daemon=True,
                         name="clock-flag-watcher").start()
