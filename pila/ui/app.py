"""Main Tkinter application window: navigation, shared state and live-view process control."""
from __future__ import annotations

import multiprocessing
import queue as queue_module
import tkinter as tk
import traceback
from pathlib import Path
from tkinter import messagebox
from typing import Dict, List, Optional, Sequence

from .. import __version__
from ..algorithms import available_algorithms
from ..database import Database
from ..errors import DatabaseError, PilaError
from ..metrics import SimulationResult
from ..models import Customer, SimulationConfig
from ..visualization import run_live_simulation
from .analytics_page import AnalyticsPage
from .history_page import HistoryPage
from .simulation_page import SimulationPage
from .style import apply_theme
from .ctk_compat import ttk


import customtkinter as ctk


class PilaApp(ctk.CTk):
    def __init__(self, db_path: Optional[str] = None) -> None:
        super().__init__()
        self.title("PILA - Intelligent Queue Simulation & Optimization")
        self.geometry("1320x840")
        self.minsize(1120, 720)
        apply_theme(self)
        self.report_callback_exception = self._on_callback_error

        self.db = Database(db_path)
        self.results: Dict[str, SimulationResult] = {}
        self._status = tk.StringVar(value="Ready.")

        self._live_proc: Optional[multiprocessing.process.BaseProcess] = None
        self._cmd_q = None
        self._out_q = None
        self._live_group = ""
        self._polling = False

        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)
        self._build_sidebar()
        content = ttk.Frame(self)
        content.grid(row=0, column=1, sticky="nsew", padx=18, pady=(16, 8))
        content.columnconfigure(0, weight=1)
        content.rowconfigure(0, weight=1)

        self.pages: Dict[str, ttk.Frame] = {}
        self.simulation_page = SimulationPage(content, self)
        self.analytics_page = AnalyticsPage(content, self)
        self.history_page = HistoryPage(content, self)
        for name, page in (("simulation", self.simulation_page), ("analytics", self.analytics_page),
                           ("history", self.history_page)):
            page.grid(row=0, column=0, sticky="nsew")
            self.pages[name] = page

        ttk.Label(self, textvariable=self._status, style="Status.TLabel", padding=(14, 6)).grid(
            row=1, column=0, columnspan=2, sticky="ew")
        self.show_page("simulation")
        self.protocol("WM_DELETE_WINDOW", self.close)

    # ------------------------------------------------------------ navigation
    def _build_sidebar(self) -> None:
        side = ttk.Frame(self, style="Side.TFrame", width=240)
        side.grid(row=0, column=0, sticky="ns")
        side.grid_propagate(False)
        brand = tk.Frame(side, bg="#211A38")
        brand.pack(fill="x", padx=18, pady=(22, 6))
        mark = tk.Canvas(brand, width=48, height=48, bg="#211A38", highlightthickness=0)
        mark.pack(side="left", padx=(0, 11))
        mark.create_oval(4, 4, 44, 44, fill="#2C2349", outline="#FF6B9D", width=2)
        mark.create_line(14, 18, 34, 18, fill="#FF6B9D", width=3, capstyle="round")
        mark.create_line(14, 24, 29, 24, fill="#FFC857", width=3, capstyle="round")
        mark.create_line(14, 30, 34, 30, fill="#71E6B1", width=3, capstyle="round")
        ttk.Label(brand, text="PILA", style="Logo.TLabel").pack(anchor="w", pady=(1, 0))
        ttk.Label(side, text="Queue simulation &\noptimization", style="CardMuted.TLabel",
                  justify="left").pack(anchor="w", padx=20, pady=(0, 24))
        self.nav: Dict[str, ttk.Button] = {}
        for key, label in (("simulation", "Simulation"), ("analytics", "Analytics"), ("history", "History")):
            btn = ttk.Button(side, text=label, style="Nav.TButton", command=lambda k=key: self.show_page(k))
            btn.pack(fill="x")
            self.nav[key] = btn
        ttk.Label(side, text=f"v{__version__}", style="CardMuted.TLabel", padding=(20, 0, 0, 14)).pack(
            side="bottom", anchor="w")

    def show_page(self, name: str) -> None:
        self.pages[name].tkraise()
        for key, btn in self.nav.items():
            btn.configure(style="NavActive.TButton" if key == name else "Nav.TButton")
        if name == "history":
            self.history_page.refresh()

    def status(self, text: str) -> None:
        self._status.set(text)

    # ----------------------------------------------------------------- helpers
    @staticmethod
    def algorithm_names() -> List[str]:
        return [cls.name for cls in available_algorithms()]

    @staticmethod
    def algorithm_keys() -> Dict[str, str]:
        return {cls.name: cls.key for cls in available_algorithms()}

    def data_dir(self) -> str:
        return str(self.db.path.parent)

    def ordered_results(self) -> List[SimulationResult]:
        return [self.results[cls.key] for cls in available_algorithms() if cls.key in self.results]

    # ----------------------------------------------------------------- results
    def register_results(self, results: Sequence[SimulationResult], goto_analytics: bool = True,
                         save: Optional[bool] = None, replace: bool = False) -> None:
        """Make ``results`` the current analysis, optionally persisting them."""
        if not results:
            return
        groups = {r.group_id for r in self.results.values()}
        if replace or (groups and groups != {results[0].group_id}):
            self.results.clear()  # never mix runs made on different customer sets
        for r in results:
            self.results[r.algorithm_key] = r
        if (self.simulation_page.autosave.get() if save is None else save):
            try:
                self.db.save_results(results)
            except DatabaseError as exc:
                messagebox.showwarning("History not saved", str(exc), parent=self)
        current = self.ordered_results()
        self.simulation_page.show_results(current)
        self.analytics_page.refresh()
        self.history_page.refresh()
        names = ", ".join(r.algorithm_name for r in results)
        self.status(f"Finished: {names}.")
        if goto_analytics:
            self.show_page("analytics")

    # --------------------------------------------------------------- live view
    @property
    def live_running(self) -> bool:
        return self._live_proc is not None and self._live_proc.is_alive()

    def launch_live(self, customers: Sequence[Customer], config: SimulationConfig, algorithm_key: str,
                    group_id: str) -> None:
        if self.live_running:
            if not messagebox.askyesno("Live simulation", "A live window is already open. Replace it?", parent=self):
                return
            self.stop_live()
        try:
            import pygame  # noqa: F401  (fail early with a friendly message)
        except ImportError:
            messagebox.showerror("Pygame missing", "Pygame is required for the live view.\n\nInstall it with:\n"
                                 "    pip install pygame", parent=self)
            return
        ctx = multiprocessing.get_context("spawn")
        self._cmd_q, self._out_q = ctx.Queue(), ctx.Queue()
        rows = [(c.id, c.arrival_time, c.service_time, c.priority) for c in customers]
        self._live_group = group_id
        self._live_proc = ctx.Process(
            target=run_live_simulation,
            args=(rows, config.to_dict(), algorithm_key, config.speed, self._cmd_q, self._out_q),
            daemon=True,
        )
        self._live_proc.start()
        self.status("Live simulation running in its own window (SPACE pause, UP/DOWN speed, R restart).")
        if not self._polling:
            self._polling = True
            self.after(200, self._poll_live)

    def send_live(self, command: str, value=None) -> None:
        if self.live_running and self._cmd_q is not None:
            self._cmd_q.put((command, value))

    def stop_live(self) -> None:
        proc = self._live_proc
        if proc is None:
            return
        if proc.is_alive():
            self.send_live("stop")
            proc.join(1.0)
            if proc.is_alive():
                proc.terminate()
                proc.join(1.0)
        self._drain_live()
        self._live_proc = None

    def _drain_live(self, timeout: float = 0.0) -> None:
        if self._out_q is None:
            return
        while True:
            try:
                kind, payload = self._out_q.get(timeout=timeout) if timeout else self._out_q.get_nowait()
            except (queue_module.Empty, OSError, ValueError):
                return
            if kind == "finished":
                payload.group_id = self._live_group
                self.register_results([payload], goto_analytics=False)
                self.status(f"Live run finished ({payload.algorithm_name}); results added to Analytics and History.")
            elif kind == "error":
                messagebox.showerror("Live simulation error", payload, parent=self)
            elif kind == "closed":
                self.status("Live window closed.")

    def _poll_live(self) -> None:
        if self.live_running:
            self._drain_live()
            self.after(200, self._poll_live)
        else:
            self._drain_live(timeout=0.3)
            self._polling = False

    # ------------------------------------------------------------------ errors
    def _on_callback_error(self, exc, val, tb) -> None:
        traceback.print_exception(exc, val, tb)
        kind = "Error" if isinstance(val, PilaError) else "Unexpected error"
        messagebox.showerror(kind, f"{type(val).__name__}: {val}", parent=self)

    def close(self) -> None:
        try:
            self.stop_live()
        finally:
            self.destroy()


def run(db_path: Optional[str] = None) -> None:
    PilaApp(db_path).mainloop()
