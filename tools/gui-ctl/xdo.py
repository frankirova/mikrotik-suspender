#!/usr/bin/env python3
"""Tiny X11 input driver (XTest) for recording GUI apps on a virtual display.

Winbox is a Qt app with no scripting interface, so the demo drives it with
synthetic pointer and keyboard events instead:

    DISPLAY=:99 xdo.py click 140 545
    DISPLAY=:99 xdo.py dclick 140 545
    DISPLAY=:99 xdo.py move 700 400
    DISPLAY=:99 xdo.py type "admin"
    DISPLAY=:99 xdo.py key Return
    DISPLAY=:99 xdo.py key ctrl+a

Events go to whatever has focus on that display; nothing touches a physical
screen. Keep this out of the app itself: it exists only for demo recordings.
"""

from __future__ import annotations

import argparse
import sys
import time

from Xlib import X, XK, display
from Xlib.ext import xtest

DISP = display.Display()
STEP_DELAY = 0.06


def _sync(pause: float = 0.12) -> None:
    DISP.sync()
    time.sleep(pause)


def move(x: int, y: int) -> None:
    xtest.fake_input(DISP, X.MotionNotify, x=x, y=y)
    _sync()


def click(x: int, y: int, button: int = 1) -> None:
    move(x, y)
    xtest.fake_input(DISP, X.ButtonPress, button)
    _sync(0.06)
    xtest.fake_input(DISP, X.ButtonRelease, button)
    _sync(0.25)


def dclick(x: int, y: int) -> None:
    click(x, y)
    time.sleep(0.05)
    click(x, y)


def _keysym_for(char: str, shift: bool) -> tuple[int, bool]:
    special = {
        "/": "slash",
        ".": "period",
        "-": "minus",
        "_": "underscore",
        ":": "colon",
        " ": "space",
        "=": "equal",
        ",": "comma",
        "@": "at",
    }
    if char in special:
        return XK.string_to_keysym(special[char]), shift
    if char.isupper():
        return XK.string_to_keysym(char.lower()), True
    return XK.string_to_keysym(char), shift


def type_text(text: str, delay: float = 0.055) -> None:
    for char in text:
        keysym, shift = _keysym_for(char, False)
        if not keysym:
            continue
        code = DISP.keysym_to_keycode(keysym)
        if not code:
            continue
        if shift:
            xtest.fake_input(DISP, X.KeyPress, DISP.keysym_to_keycode(XK.XK_Shift_L))
        xtest.fake_input(DISP, X.KeyPress, code)
        xtest.fake_input(DISP, X.KeyRelease, code)
        if shift:
            xtest.fake_input(DISP, X.KeyRelease, DISP.keysym_to_keycode(XK.XK_Shift_L))
        DISP.sync()
        time.sleep(delay)


def key(name: str) -> None:
    mods = {
        "ctrl": XK.XK_Control_L,
        "alt": XK.XK_Alt_L,
        "shift": XK.XK_Shift_L,
    }
    parts = name.split("+")
    held = []
    for part in parts[:-1]:
        code = DISP.keysym_to_keycode(mods[part.lower()])
        xtest.fake_input(DISP, X.KeyPress, code)
        held.append(code)
    main = parts[-1]
    keysym = XK.string_to_keysym(main) or XK.string_to_keysym(main.lower())
    code = DISP.keysym_to_keycode(keysym)
    xtest.fake_input(DISP, X.KeyPress, code)
    _sync(0.03)
    xtest.fake_input(DISP, X.KeyRelease, code)
    for code in reversed(held):
        xtest.fake_input(DISP, X.KeyRelease, code)
    _sync(0.1)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    p_click = sub.add_parser("click")
    p_click.add_argument("x", type=int)
    p_click.add_argument("y", type=int)
    p_dclick = sub.add_parser("dclick")
    p_dclick.add_argument("x", type=int)
    p_dclick.add_argument("y", type=int)
    p_move = sub.add_parser("move")
    p_move.add_argument("x", type=int)
    p_move.add_argument("y", type=int)
    p_type = sub.add_parser("type")
    p_type.add_argument("text")
    p_key = sub.add_parser("key")
    p_key.add_argument("name")
    args = parser.parse_args()

    if args.action == "click":
        click(args.x, args.y)
    elif args.action == "dclick":
        dclick(args.x, args.y)
    elif args.action == "move":
        move(args.x, args.y)
    elif args.action == "type":
        type_text(args.text)
    elif args.action == "key":
        key(args.name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
