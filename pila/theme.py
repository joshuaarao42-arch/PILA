"""Shared colour palette (used by Tkinter, Matplotlib and Pygame)."""
from typing import Tuple

COLORS = {
    "bg": "#171326",
    "surface": "#211A38",
    "surface2": "#2C2349",
    "border": "#4B3B70",
    "text": "#FAF7FF",
    "muted": "#B9AECC",
    "accent": "#FF6B9D",   # coral pink
    "amber": "#FFC857",
    "green": "#71E6B1",
    "red": "#FF7B7B",
    "purple": "#A88BFF",
    "pink": "#FF9BD0",
    "lavender": "#C4B5FD",
}

ALGO_COLORS = {"fcfs": "#FF6B9D", "priority": "#A88BFF", "sjf": "#71E6B1", "rr": "#FFC857"}

#: priority 1..5 (1 = most urgent)
PRIORITY_COLORS = ["#FF7B7B", "#FF9F68", "#FFC857", "#8ED8FF", "#C4B5FD"]


def hex_to_rgb(value: str) -> Tuple[int, int, int]:
    value = value.lstrip("#")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def priority_color(priority: int) -> str:
    return PRIORITY_COLORS[min(max(priority, 1), len(PRIORITY_COLORS)) - 1]
