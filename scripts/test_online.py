#!/usr/bin/env python3
"""Online play test: two SocketIO clients quick-match, play, resign.

Verifies matchmaking, room events, server-authoritative moves, clocks and
Elo updates — without a browser.
"""
from __future__ import annotations

import queue
import re
import sys
import threading
import time

import requests
import socketio

BASE = "http://127.0.0.1:15989"

PASS, FAIL = [], []


def check(name: str, cond: bool, detail: str = "") -> None:
    (PASS if cond else FAIL).append(name)
    print(f"[{'OK ' if cond else 'FAIL'}] {name}" + (f" — {detail}" if detail and not cond else ""))


def csrf(s: requests.Session) -> str:
    r = s.get(f"{BASE}/")
    m = re.search(r'name="csrf-token" content="([^"]+)"', r.text)
    return m.group(1) if m else ""


def register(name: str) -> requests.Session:
    s = requests.Session()
    r = s.get(f"{BASE}/register")
    token = re.search(r'name="csrf-token" content="([^"]+)"', r.text).group(1)
    s.post(f"{BASE}/register", data={
        "username": name, "password": "secret123",
        "confirm": "secret123", "csrf_token": token,
    })
    s.headers["X-CSRFToken"] = token
    return s


class Player:
    def __init__(self, session: requests.Session, name: str):
        self.name = name
        self.session = session
        self.events: queue.Queue = queue.Queue()
        self.client = socketio.Client(http_session=session)
        self.color = None
        self.game_id = None

        @self.client.on("game:started")
        def on_started(data):
            self.game_id = data["game_id"]
            self.color = ("white" if data["white"]["username"] == name
                          else "black")
            self.events.put(("started", data))

        @self.client.on("game:move")
        def on_move(data):
            self.events.put(("move", data))

        @self.client.on("game:over")
        def on_over(data):
            self.events.put(("over", data))

        @self.client.on("game:chat")
        def on_chat(data):
            self.events.put(("chat", data))

        @self.client.on("game:draw:offered")
        def on_draw(data):
            self.events.put(("draw", data))

    def connect(self) -> None:
        self.client.connect(BASE, transports=["polling"])

    def emit(self, event: str, data: dict) -> None:
        self.client.emit(event, data)

    def wait_for(self, kind: str, timeout: float = 10.0):
        deadline = time.time() + timeout
        stash = []
        while time.time() < deadline:
            try:
                got = self.events.get(timeout=max(0.1, deadline - time.time()))
            except queue.Empty:
                break
            if got[0] == kind:
                return got[1]
            stash.append(got)
        for item in stash:
            self.events.put(item)
        return None


def main() -> int:
    stamp = int(time.time()) % 100000
    alice = register(f"alice{stamp}")
    bob = register(f"bob{stamp}")

    pa = Player(alice, f"alice{stamp}")
    pb = Player(bob, f"bob{stamp}")
    pa.connect()
    pb.connect()
    time.sleep(0.5)

    rating_before = alice.get(f"{BASE}/api/me").json()["rating"]

    # quick match
    pa.emit("quick:join", {"tc": "5+0", "rated": True})
    pb.emit("quick:join", {"tc": "5+0", "rated": True})
    started_a = pa.wait_for("started")
    started_b = pb.wait_for("started")
    check("quick match paired", started_a is not None and started_b is not None)
    check("same game both players",
          started_a["game_id"] == started_b["game_id"])

    # play 4 plies
    moves = ["e2e4", "e7e5", "g1f3", "b8c6", "f1c4", "g8f6"]
    for uci in moves:
        mover = pa if ((pa.color == "white") == (moves.index(uci) % 2 == 0)) else pb
        mover.emit("game:move", {"game_id": pa.game_id, "uci": uci})
        got_a = pa.wait_for("move", timeout=6)
        got_b = pb.wait_for("move", timeout=6)
        if got_a is None or got_b is None:
            check(f"move {uci} broadcast", False)
            break
    else:
        check("6 plies broadcast to both", True)

    # clocks present in the last state
    state = alice.get(f"{BASE}/api/games/{pa.game_id}").json()
    check("clocks present (5+0)", bool(state.get("clocks")), str(state.get("clocks"))[:80])

    # chat
    pa.emit("game:chat", {"game_id": pa.game_id, "text": "Привет, боб!"})
    chat_b = pb.wait_for("chat", timeout=5)
    check("chat delivered", chat_b is not None and chat_b.get("text") == "Привет, боб!")

    # draw offer -> decline -> resign
    pa.emit("game:draw:offer", {"game_id": pa.game_id})
    draw_b = pb.wait_for("draw", timeout=5)
    check("draw offer delivered", draw_b is not None)
    pb.emit("game:draw:decline", {"game_id": pa.game_id})
    time.sleep(0.3)
    pb.emit("game:resign", {"game_id": pa.game_id})
    over_a = pa.wait_for("over", timeout=6)
    over_b = pb.wait_for("over", timeout=6)
    check("game over on resign", over_a is not None and over_b is not None,
          str(over_a))
    check("resign result 1-0/0-1", over_a and over_a.get("result") in ("1-0", "0-1"),
          str(over_a and over_a.get("result")))

    # Elo changed for the winner
    time.sleep(0.5)
    rating_after = alice.get(f"{BASE}/api/me").json()["rating"]
    expected_winner = "white" if over_a["result"] == "1-0" else "black"
    if pa.color == expected_winner:
        check("Elo updated for winner", rating_after > rating_before,
              f"{rating_before} -> {rating_after}")
    else:
        check("Elo updated for loser", rating_after < rating_before,
              f"{rating_before} -> {rating_after}")

    pa.client.disconnect()
    pb.client.disconnect()

    print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
    if FAIL:
        print("FAILED:", ", ".join(FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
