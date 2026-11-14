#!/usr/bin/env python3
"""Mock OpenAI-compatible LLM server for offline testing of the AI opponent.

Listens on 127.0.0.1:15990 and implements POST /v1/chat/completions.
Behaviour (scripted, no model needed):
- 1st request of a game: replies with an ILLEGAL move (e2e4-ish gibberish)
  to exercise the retry mechanism... actually replies with "zz99" token
- 2nd+: parses the last legal-moves list from the prompt and plays the first
  legal move, with a short chat line.

Point LM Studio / compat provider at http://127.0.0.1:15990/v1 to test.
"""
from __future__ import annotations

import re
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

STATE = {"calls": 0, "lock": threading.Lock()}


def first_legal_from_prompt(prompt: str) -> str:
    match = re.search(r"UCI: ([a-z0-9, ]+)", prompt)
    if not match:
        return "e2e4"
    moves = [m for m in match.group(1).split(",") if m.strip()]
    if not moves:
        return "e2e4"
    return moves[0].strip()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # quiet
        pass

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8", "replace")
        with STATE["lock"]:
            # a player message is only present in the FIRST call of a turn;
            # the corrective retry prompt never contains it
            if "The player says to you:" in body:
                STATE["calls"] = 1
            else:
                STATE["calls"] += 1
            call = STATE["calls"]

        if call == 1:
            # deliberately illegal to test the retry flow
            content = "MOVE: zz99\nCHAT: Ha! My first move is a mystery even to me!"
        else:
            move = first_legal_from_prompt(body)
            content = f"MOVE: {move}\nCHAT: Calculated instantly, as always. Your turn!"

        payload = (
            '{"choices":[{"message":{"role":"assistant","content":'
            + repr(content).replace("'", '"') + "}}]}"
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


if __name__ == "__main__":
    print("Mock LLM on http://127.0.0.1:15990/v1 (Ctrl+C to stop)")
    HTTPServer(("127.0.0.1", 15990), Handler).serve_forever()
