"""ANSI terminal colors used by the logger and menus."""

from __future__ import annotations


class Color:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    INFO    = "\033[96m"
    WARNING = "\033[93m"
    ERROR   = "\033[91m"
    SUCCESS = "\033[92m"
    MENU    = "\033[95m"
