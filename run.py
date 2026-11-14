#!/usr/bin/env python3
"""botyarachess entry point: run the app on 0.0.0.0:15989.

Usage:
    .venv/bin/python run.py            # normal run
    .venv/bin/python run.py --debug    # auto-reload + verbose errors
"""
from __future__ import annotations

import argparse

from botyarachess import create_app
from botyarachess.config import HOST, PORT
from botyarachess.extensions import socketio


def main() -> None:
    parser = argparse.ArgumentParser(description="botyarachess server")
    parser.add_argument("--debug", action="store_true", help="enable Flask debug mode")
    parser.add_argument("--port", type=int, default=PORT)
    parser.add_argument("--host", default=HOST)
    args = parser.parse_args()

    app = create_app()
    socketio.run(
        app,
        host=args.host,
        port=args.port,
        debug=args.debug,
        use_reloader=args.debug,
        allow_unsafe_werkzeug=True,  # intended for trusted LAN usage
    )


if __name__ == "__main__":
    main()
