#!/usr/bin/env python3
"""End-to-end backend test for botyarachess (requires the server running on
15989 and scripts/mock_llm.py on 15990 for the AI-provider test).

Covers: registration, login, settings, hotseat play to checkmate, PGN,
engine review, AI game via the mock OpenAI-compatible provider (including
the illegal-move retry), and the manual paste-mode.
"""
from __future__ import annotations

import re
import sys
import time

import requests

BASE = "http://127.0.0.1:15989"
MOCK = "http://127.0.0.1:15990"

PASS = []
FAIL = []


def check(name: str, condition: bool, detail: str = "") -> None:
    (PASS if condition else FAIL).append(name)
    mark = "OK " if condition else "FAIL"
    print(f"[{mark}] {name}" + (f" — {detail}" if detail and not condition else ""))


def csrf_from(response) -> str:
    match = re.search(r'name="csrf-token" content="([^"]+)"', response.text)
    return match.group(1) if match else ""


def register_and_login(username: str, password: str = "secret123") -> requests.Session:
    s = requests.Session()
    r = s.get(f"{BASE}/register")
    token = csrf_from(r)
    r = s.post(f"{BASE}/register", data={
        "username": username, "password": password,
        "confirm": password, "csrf_token": token,
    })
    # API POSTs need the CSRF header, exactly like the browser client does
    s.headers["X-CSRFToken"] = token
    return s


def main() -> int:
    # ------------------------------------------------------------- auth
    username = f"tester{int(time.time()) % 100000}"
    s = register_and_login(username)
    check("register+login", "csrf-token" in s.get(f"{BASE}/").text)

    me = s.get(f"{BASE}/api/me").json()
    check("api/me", me.get("username") == username, str(me))

    # settings
    r = s.post(f"{BASE}/api/settings", json={
        "theme": "catppuccin-mocha", "locale": "ru",
        "settings": {"sounds": False},
    })
    check("save settings", r.ok)
    me = s.get(f"{BASE}/api/me").json()
    check("settings persisted",
          me["theme"] == "catppuccin-mocha" and me["locale"] == "ru"
          and me["settings"]["sounds"] is False)

    # ---------------------------------------------------------- hotseat
    game_id = s.post(f"{BASE}/api/games/hotseat").json()["game_id"]
    state = s.get(f"{BASE}/api/games/{game_id}").json()
    check("hotseat created", state["mode"] == "hotseat")

    moves = ["e2e4", "e7e5", "d1h5", "b8c6", "f1c4", "g8f6", "h5f7"]
    last = None
    for uci in moves:
        last = s.post(f"{BASE}/api/games/{game_id}/move", json={"uci": uci})
        if not last.ok:
            print(f"    move {uci} -> {last.status_code}: {last.text[:200]}")
            break
    last = last.json()
    check("scholar's mate played", last["status"] == "finished"
          and last["result"] == "1-0" and last["termination"] == "checkmate",
          str(last.get("result")))
    illegal = s.post(f"{BASE}/api/games/{game_id}/move", json={"uci": "a2a3"})
    check("move after game over rejected", illegal.status_code == 400)

    # undo is refused after game end, pgn works
    pgn = s.get(f"{BASE}/api/games/{game_id}/pgn").text
    check("pgn export", "1. e4" in pgn and "1-0" in pgn)

    # history
    hist = s.get(f"{BASE}/api/games").json()["games"]
    check("history contains game", any(g["id"] == game_id for g in hist))

    # ------------------------------------------------------- review
    r = s.post(f"{BASE}/api/games/{game_id}/review/start", json={"speed": "fast"}).json()
    check("review started (stockfish)", r.get("available") is True, str(r))
    if r.get("available"):
        for _ in range(120):
            status = s.get(f"{BASE}/api/review/status/{r['job_id']}").json()
            if status.get("done"):
                break
            time.sleep(0.3)
        check("review finished", status.get("done") and not status.get("error"),
              str(status.get("error")))
        analysis = s.get(f"{BASE}/api/games/{game_id}/analysis").json()["analysis"]
        check("review has plies", len(analysis["plies"]) == 7, str(len(analysis["plies"])))
        check("review accuracy", analysis["accuracy"]["white"] > 0)

    # --------------------------------------------- AI via mock provider
    import threading
    import socket as _socket

    def ensure_mock() -> bool:
        try:
            _socket.create_connection(("127.0.0.1", 15990), timeout=1).close()
            return True
        except OSError:
            return False

    if not ensure_mock():
        print("[i ] mock LLM not running — start scripts/mock_llm.py to cover this block")
    else:
        s.post(f"{BASE}/api/settings/ai", json={
            "provider": "compat", "base_url": f"{MOCK}/v1",
            "model": "mock-model", "api_key": "test-key",
            "persona": "trash", "chat_enabled": True,
        })
        ai_id = s.post(f"{BASE}/api/games/ai", json={"color": "white"}).json()["game_id"]
        resp = s.post(f"{BASE}/api/games/{ai_id}/move", json={
            "uci": "e2e4", "message": "Привет! Сыграем?"}).json()
        check("AI retry: illegal first answer fixed",
              resp.get("ai_move", {}).get("uci") not in (None, "zz99"),
              str(resp.get("ai_move")))
        check("AI chat present", bool(resp.get("ai_chat")), str(resp.get("ai_chat")))
        check("AI attempts >= 2", resp.get("ai_attempts", 0) >= 2, str(resp.get("ai_attempts")))
        state = s.get(f"{BASE}/api/games/{ai_id}").json()
        check("AI game state has chat", len(state.get("chat", [])) >= 2)

        # ------------------------------------ manual paste-mode
        s.post(f"{BASE}/api/settings/ai", json={"provider": "manual"})
        man_id = s.post(f"{BASE}/api/games/ai", json={"color": "black"}).json()["game_id"]
        # AI plays white first: ask for prompt
        nudged = s.post(f"{BASE}/api/games/{man_id}/move", json={"uci": ""})
        check("manual nudge ok", nudged.ok and nudged.json().get("need_prompt") is True,
              str(nudged.text[:200]))
        prompt = s.get(f"{BASE}/api/games/{man_id}/manual_prompt").json()["prompt"]
        check("manual prompt built", "FEN:" in prompt and "MOVE:" in prompt
              and "по-русски" not in prompt and "Russian" in prompt)

        bad = s.post(f"{BASE}/api/games/{man_id}/manual_reply", json={
            "text": "MOVE: zz99\nCHAT: ой"})
        check("manual illegal reply rejected", bad.status_code == 400
              and "retry_prompt" in bad.json())
        retry = bad.json()["retry_prompt"]
        check("retry prompt mentions illegality", "ILLEGAL" in retry)
        # answer with the first legal move listed in the retry prompt
        uci_match = re.search(r"UCI: ([a-z0-9, ]+)", retry)
        first_legal = uci_match.group(1).split(",")[0].strip()
        good = s.post(f"{BASE}/api/games/{man_id}/manual_reply", json={
            "text": f"MOVE: {first_legal}\nCHAT: Начали!"})
        check("manual legal reply applied", good.ok
              and good.json()["status"] == "active", good.text[:200])

    # --------------------------------------------------------- misc
    engine = s.get(f"{BASE}/api/engine/status").json()
    check("engine detected", engine.get("available") is True, str(engine))

    print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
    if FAIL:
        print("FAILED:", ", ".join(FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
