"""Simulation page: configure, generate customers, run live / instantly / compare."""
from __future__ import annotations

import math
import tkinter as tk
from dataclasses import replace
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog
from typing import List, Optional, Sequence, Tuple

from ..algorithms import available_algorithms
from ..engine import compare_algorithms, new_group_id, run_simulation
from ..errors import PilaError
from ..generator import generate_customers, load_customers_csv, save_customers_csv
from ..metrics import SimulationResult
from ..models import Customer, SimulationConfig
from .widgets import DataTable
from .ctk_compat import ttk

FIELDS = [
    ("num_customers", "Customers"),
    ("num_counters", "Service counters"),
    ("mean_interarrival", "Mean inter-arrival time"),
    ("min_service", "Min service time"),
    ("max_service", "Max service time"),
    ("priority_levels", "Priority levels (1-5)"),
    ("time_quantum", "Round Robin quantum"),
    ("seed", "Seed (blank = random)"),
]
SPEED_MIN, SPEED_MAX = 0.25, 32.0


def _speed_from_pos(pos: float) -> float:
    return round(SPEED_MIN * (SPEED_MAX / SPEED_MIN) ** float(pos), 2)


def _pos_from_speed(speed: float) -> float:
    speed = max(SPEED_MIN, min(SPEED_MAX, speed))
    return math.log(speed / SPEED_MIN) / math.log(SPEED_MAX / SPEED_MIN)


class SimulationPage(ttk.Frame):
    def __init__(self, master, app) -> None:
        super().__init__(master)
        self.app = app
        defaults = SimulationConfig()
        self.vars = {name: tk.StringVar(value="" if name == "seed" else f"{getattr(defaults, name):g}")
                     for name, _ in FIELDS}
        self.algorithms = {cls.name: cls.key for cls in available_algorithms()}
        self.algo_var = tk.StringVar(value=next(iter(self.algorithms)))
        self.speed_var = tk.DoubleVar(value=_pos_from_speed(defaults.speed))
        self.speed_label = tk.StringVar(value=f"{defaults.speed:g}x")
        self.autosave = tk.BooleanVar(value=True)
        self.preset_var = tk.StringVar()
        self.source_text = tk.StringVar(value="No customers yet - they are generated automatically when you run.")

        self._customers: Optional[List[Customer]] = None
        self._signature: Optional[tuple] = None
        self._from_csv = False
        self.scenario_id = new_group_id()

        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)
        self._build_config_card()
        self._build_right_side()
        self.refresh_presets()

    # ---------------------------------------------------------------- layout
    def _build_config_card(self) -> None:
        card = ttk.Frame(self, style="Card.TFrame", width=350)
        card.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        card.columnconfigure(0, weight=1)
        card.columnconfigure(1, weight=0)
        ttk.Label(card, text="Configuration", style="CardTitle.TLabel").grid(
            row=0, column=0, columnspan=2, sticky="w", padx=18, pady=(18, 4))

        row = 1
        for name, label in FIELDS:
            ttk.Label(card, text=label, style="Card.TLabel", width=175, wraplength=165,
                      anchor="w", justify="left").grid(
                row=row, column=0, sticky="w", pady=(9, 0), padx=(18, 8))
            ttk.Entry(card, textvariable=self.vars[name], width=112, justify="right").grid(
                row=row, column=1, sticky="e", pady=(9, 0), padx=(4, 18))
            row += 1
        ttk.Button(card, text="Random seed", command=self.randomize_seed).grid(
            row=row, column=1, sticky="e", pady=(6, 0), padx=(4, 18))
        row += 1

        ttk.Label(card, text="Simulation speed", style="Card.TLabel").grid(
            row=row, column=0, sticky="w", pady=(12, 0), padx=(18, 8))
        ttk.Label(card, textvariable=self.speed_label, style="Card.TLabel").grid(
            row=row, column=1, sticky="e", pady=(12, 0), padx=(4, 18))
        row += 1
        ttk.Scale(card, from_=0, to=1, variable=self.speed_var, command=self._on_speed).grid(
            row=row, column=0, columnspan=2, sticky="ew", pady=(2, 0), padx=18)
        row += 1

        ttk.Label(card, text="Algorithm (live view)", style="Card.TLabel").grid(
            row=row, column=0, sticky="w", pady=(12, 0), padx=(18, 8))
        ttk.Combobox(card, textvariable=self.algo_var, values=list(self.algorithms), state="readonly",
                     width=145).grid(row=row, column=1, sticky="e", pady=(12, 0), padx=(4, 18))
        row += 1

        ttk.Label(card, text="Saved preset", style="Card.TLabel").grid(
            row=row, column=0, sticky="w", pady=(12, 0), padx=(18, 8))
        self.preset_box = ttk.Combobox(card, textvariable=self.preset_var, width=145, state="readonly")
        self.preset_box.grid(row=row, column=1, sticky="e", pady=(12, 0), padx=(4, 18))
        row += 1
        preset_row = ttk.Frame(card, style="Card.TFrame")
        preset_row.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        for i, (text, cmd) in enumerate((("Load", self.load_preset), ("Save as...", self.save_preset),
                                         ("Delete", self.delete_preset))):
            ttk.Button(preset_row, text=text, command=cmd).grid(row=0, column=i, padx=(0 if i == 0 else 6, 0))
        row += 1

        ttk.Checkbutton(card, text="Save runs to history", variable=self.autosave).grid(
            row=row, column=0, columnspan=2, sticky="w", pady=(14, 4))
        row += 1

        ttk.Button(card, text="Launch Live Simulation", style="Accent.TButton", command=self.launch_live).grid(
            row=row, column=0, columnspan=2, sticky="ew", pady=(8, 0), padx=18)
        row += 1
        ttk.Button(card, text="Compare All Algorithms", command=self.compare_all).grid(
            row=row, column=0, columnspan=2, sticky="ew", pady=(6, 0), padx=18)
        row += 1
        ttk.Button(card, text="Run Selected Instantly", command=self.run_instant).grid(
            row=row, column=0, columnspan=2, sticky="ew", pady=(6, 0), padx=18)
        row += 1
        live = ttk.Frame(card, style="Card.TFrame")
        live.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(6, 18), padx=18)
        live.columnconfigure((0, 1), weight=1)
        ttk.Button(live, text="Pause / Resume", command=lambda: self.app.send_live("toggle_pause")).grid(row=0, column=0, sticky="ew")
        ttk.Button(live, text="Close live window", style="Danger.TButton", command=self.app.stop_live).grid(
            row=0, column=1, sticky="ew", padx=(6, 0))

    def _build_right_side(self) -> None:
        right = ttk.Frame(self)
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure(0, weight=3)
        right.rowconfigure(1, weight=2)

        top = ttk.Frame(right, style="Card.TFrame", padding=16)
        top.grid(row=0, column=0, sticky="nsew", pady=(0, 14))
        top.columnconfigure(0, weight=1)
        top.rowconfigure(2, weight=1)
        head = ttk.Frame(top, style="Card.TFrame")
        head.grid(row=0, column=0, sticky="ew")
        head.columnconfigure(0, weight=1)
        ttk.Label(head, text="Customer set", style="CardTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Button(head, text="Generate new", command=self.generate).grid(row=0, column=1, padx=(0, 6))
        ttk.Button(head, text="Import CSV...", command=self.import_csv).grid(row=0, column=2, padx=(0, 6))
        ttk.Button(head, text="Save CSV...", command=self.export_customers).grid(row=0, column=3)
        ttk.Label(top, textvariable=self.source_text, style="CardMuted.TLabel").grid(row=1, column=0, sticky="w", pady=(4, 8))
        self.customer_table = DataTable(top, [("id", "ID", 60, "center"), ("arrival", "Arrival", 100, "center"),
                                              ("service", "Service", 100, "center"), ("priority", "Priority", 100, "center")],
                                        height=8)
        self.customer_table.grid(row=2, column=0, sticky="nsew")

        bottom = ttk.Frame(right, style="Card.TFrame", padding=16)
        bottom.grid(row=1, column=0, sticky="nsew")
        bottom.columnconfigure(0, weight=1)
        bottom.rowconfigure(1, weight=1)
        ttk.Label(bottom, text="Latest results", style="CardTitle.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 8))
        self.results_table = DataTable(bottom, [
            ("alg", "Algorithm", 130, "w"), ("wait", "Avg wait", 90, "center"), ("tat", "Avg turnaround", 110, "center"),
            ("maxq", "Max queue", 90, "center"), ("util", "Utilization", 90, "center"), ("served", "Served", 80, "center")],
            height=4)
        self.results_table.grid(row=1, column=0, sticky="nsew")

    # ------------------------------------------------------------ configuration
    def current_speed(self) -> float:
        return _speed_from_pos(self.speed_var.get())

    def _on_speed(self, _value=None) -> None:
        speed = self.current_speed()
        self.speed_label.set(f"{speed:g}x")
        self.app.send_live("speed", speed)

    def read_config(self) -> Optional[SimulationConfig]:
        data = {name: var.get() for name, var in self.vars.items()}
        data["speed"] = self.current_speed()
        try:
            return SimulationConfig.from_dict(data)
        except PilaError as exc:
            messagebox.showerror("Invalid configuration", str(exc), parent=self)
            return None

    def apply_config(self, cfg: SimulationConfig) -> None:
        for name, _ in FIELDS:
            value = getattr(cfg, name)
            self.vars[name].set("" if value is None else f"{value:g}" if isinstance(value, float) else str(value))
        self.speed_var.set(_pos_from_speed(cfg.speed))
        self.speed_label.set(f"{self.current_speed():g}x")
        self._from_csv = False

    # --------------------------------------------------------------- scenarios
    def ensure_scenario(self) -> Optional[Tuple[SimulationConfig, List[Customer]]]:
        cfg = self.read_config()
        if cfg is None:
            return None
        if self._from_csv and self._customers:
            return replace(cfg, num_customers=len(self._customers)), self._customers
        try:
            signature = (cfg.num_customers, cfg.mean_interarrival, cfg.min_service, cfg.max_service,
                         cfg.priority_levels, cfg.seed)
            if self._customers is None or cfg.seed is None or signature != self._signature:
                cfg = cfg.ensure_seed()
                self.vars["seed"].set(str(cfg.seed))
                self._customers = generate_customers(cfg)
                self._signature = (cfg.num_customers, cfg.mean_interarrival, cfg.min_service,
                                   cfg.max_service, cfg.priority_levels, cfg.seed)
                self.scenario_id = new_group_id()
                self._show_customers(f"Generated - seed {cfg.seed} - {len(self._customers)} customers")
        except PilaError as exc:
            messagebox.showerror("Could not generate customers", str(exc), parent=self)
            return None
        return cfg, self._customers

    def _show_customers(self, caption: str) -> None:
        self.source_text.set(caption)
        self.customer_table.clear()
        for c in self._customers or []:
            self.customer_table.add((c.id, f"{c.arrival_time:g}", f"{c.service_time:g}", f"P{c.priority}"))

    def generate(self) -> None:
        self._from_csv = False
        self._customers = None
        if self.ensure_scenario():
            self.app.status(f"Generated {len(self._customers)} customers.")

    def randomize_seed(self) -> None:
        self.vars["seed"].set("")
        self.generate()

    def import_csv(self) -> None:
        path = filedialog.askopenfilename(parent=self, title="Import customers", initialdir=self.app.data_dir(),
                                          filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
        if not path:
            return
        try:
            customers = load_customers_csv(path)
        except PilaError as exc:
            messagebox.showerror("Import failed", str(exc), parent=self)
            return
        self._customers = customers
        self._from_csv = True
        self.scenario_id = new_group_id()
        self.vars["num_customers"].set(str(len(customers)))
        self._show_customers(f"Imported from {Path(path).name} - {len(customers)} customers "
                             "(click 'Generate new' to return to random data)")
        self.app.status(f"Imported {len(customers)} customers from {Path(path).name}.")

    def export_customers(self) -> None:
        scenario = self.ensure_scenario()
        if scenario is None:
            return
        path = filedialog.asksaveasfilename(parent=self, title="Save customers", defaultextension=".csv",
                                            initialfile="customers.csv", filetypes=[("CSV files", "*.csv")])
        if not path:
            return
        try:
            save_customers_csv(scenario[1], path)
        except OSError as exc:
            messagebox.showerror("Save failed", str(exc), parent=self)
            return
        self.app.status(f"Saved customers to {path}")

    # --------------------------------------------------------------------- runs
    def _selected_key(self) -> str:
        return self.algorithms[self.algo_var.get()]

    def run_instant(self) -> None:
        scenario = self.ensure_scenario()
        if scenario is None:
            return
        cfg, customers = scenario
        try:
            result = run_simulation(customers, cfg, self._selected_key(), self.scenario_id)
        except PilaError as exc:
            messagebox.showerror("Simulation failed", str(exc), parent=self)
            return
        self.app.register_results([result], goto_analytics=True)

    def compare_all(self) -> None:
        scenario = self.ensure_scenario()
        if scenario is None:
            return
        cfg, customers = scenario
        try:
            results = compare_algorithms(customers, cfg, group_id=self.scenario_id)
        except PilaError as exc:
            messagebox.showerror("Simulation failed", str(exc), parent=self)
            return
        self.app.register_results(results, goto_analytics=True)

    def launch_live(self) -> None:
        scenario = self.ensure_scenario()
        if scenario is None:
            return
        cfg, customers = scenario
        self.app.launch_live(customers, cfg, self._selected_key(), self.scenario_id)

    # ----------------------------------------------------------------- results
    def show_results(self, results: Sequence[SimulationResult]) -> None:
        self.results_table.clear()
        if not results:
            return
        best = min(r.summary.avg_waiting_time for r in results)
        for r in results:
            s = r.summary
            tag = ("best",) if len(results) > 1 and s.avg_waiting_time == best else ()
            self.results_table.add((r.algorithm_name, f"{s.avg_waiting_time:.2f}", f"{s.avg_turnaround_time:.2f}",
                                    s.max_queue_length, f"{s.utilization * 100:.1f}%", s.total_served), tags=tag)

    # ----------------------------------------------------------------- presets
    def refresh_presets(self) -> None:
        try:
            names = self.app.db.list_configs()
        except PilaError as exc:
            names = []
            self.app.status(str(exc))
        self.preset_box.configure(values=names)
        if self.preset_var.get() not in names:
            self.preset_var.set("")

    def save_preset(self) -> None:
        cfg = self.read_config()
        if cfg is None:
            return
        name = simpledialog.askstring("Save preset", "Preset name:", initialvalue=self.preset_var.get(), parent=self)
        if not name:
            return
        try:
            self.app.db.save_config(name, cfg)
        except PilaError as exc:
            messagebox.showerror("Could not save preset", str(exc), parent=self)
            return
        self.refresh_presets()
        self.preset_var.set(name.strip())
        self.app.status(f"Preset '{name.strip()}' saved.")

    def load_preset(self) -> None:
        name = self.preset_var.get()
        if not name:
            messagebox.showinfo("Load preset", "Choose a preset first.", parent=self)
            return
        try:
            self.apply_config(self.app.db.load_config(name))
        except PilaError as exc:
            messagebox.showerror("Could not load preset", str(exc), parent=self)
            return
        self.generate()

    def delete_preset(self) -> None:
        name = self.preset_var.get()
        if not name:
            return
        if messagebox.askyesno("Delete preset", f"Delete preset '{name}'?", parent=self):
            try:
                self.app.db.delete_config(name)
            except PilaError as exc:
                messagebox.showerror("Error", str(exc), parent=self)
                return
            self.refresh_presets()
