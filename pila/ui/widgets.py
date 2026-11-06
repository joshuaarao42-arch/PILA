"""Reusable Tkinter widgets."""
from __future__ import annotations

import tkinter as tk
from .ctk_compat import ttk
from typing import Callable, Iterable, Sequence, Tuple

import pandas as pd
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from ..theme import COLORS
from . import charts


class MetricCard(ttk.Frame):
    """A KPI tile: coloured accent bar, caption and a large value."""

    def __init__(self, master, title: str, accent: str) -> None:
        super().__init__(master, style="Card.TFrame", padding=(14, 12))
        tk.Frame(self, bg=accent, width=4).pack(side="left", fill="y", padx=(0, 12))
        body = ttk.Frame(self, style="Card.TFrame")
        body.pack(side="left", fill="both", expand=True)
        ttk.Label(body, text=title, style="CardMuted.TLabel").pack(anchor="w")
        self.value = ttk.Label(body, text="-", style="CardValue.TLabel")
        self.value.pack(anchor="w")
        self.sub = ttk.Label(body, text="", style="CardMuted.TLabel")
        self.sub.pack(anchor="w")

    def set(self, value: str, sub: str = "") -> None:
        self.value.configure(text=value)
        self.sub.configure(text=sub)


class ChartTab(ttk.Frame):
    """Hosts one Matplotlib figure; ``draw`` is a function from :mod:`charts`."""

    def __init__(self, master, draw: Callable, figsize=(8, 5)) -> None:
        super().__init__(master, style="Card.TFrame")
        self.draw = draw
        self.figure = charts.new_figure(figsize)
        self.canvas = FigureCanvasTkAgg(self.figure, master=self)
        widget = self.canvas.get_tk_widget()
        widget.configure(bg=COLORS["surface"], highlightthickness=0)
        widget.pack(fill="both", expand=True, padx=6, pady=6)

    def redraw(self, data) -> None:
        self.draw(self.figure, data)
        self.canvas.draw_idle()


class DataTable(ttk.Frame):
    """A scrollable Treeview that can display a pandas DataFrame or custom rows."""

    def __init__(self, master, columns: Sequence[Tuple[str, str, int, str]], height: int = 8,
                 selectmode: str = "browse") -> None:
        super().__init__(master, style="Card.TFrame")
        self.tree = ttk.Treeview(self, columns=[c[0] for c in columns], show="headings", height=height,
                                 selectmode=selectmode)
        for key, heading, width, anchor in columns:
            self.tree.heading(key, text=heading)
            self.tree.column(key, width=width, anchor=anchor, stretch=True)
        scroll = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.tree.tag_configure("best", foreground=COLORS["green"])

    def clear(self) -> None:
        self.tree.delete(*self.tree.get_children())

    def add(self, values: Iterable, iid: str = None, tags: Tuple[str, ...] = ()) -> None:
        self.tree.insert("", "end", iid=iid, values=list(values), tags=tags)

    def selected(self) -> Tuple[str, ...]:
        return self.tree.selection()

    def load_dataframe(self, df: pd.DataFrame) -> None:
        """Replace columns and rows with those of ``df``."""
        self.clear()
        cols = [str(c) for c in df.columns]
        self.tree.configure(columns=cols)
        for col in cols:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=100, anchor="center", stretch=True)
        for row in df.itertuples(index=False):
            self.add(row)
