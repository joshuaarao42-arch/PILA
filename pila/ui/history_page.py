"""History page: browse saved runs (SQLite -> Pandas), reload, delete, export."""
from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox

from ..analytics import export_history_csv, history_algorithm_averages
from ..errors import PilaError
from ..sample_data import seed_sample_history
from . import charts
from .widgets import ChartTab, DataTable
from .ctk_compat import ttk


class HistoryPage(ttk.Frame):
    ALL = "All algorithms"

    def __init__(self, master, app) -> None:
        super().__init__(master)
        self.app = app
        self.filter_var = tk.StringVar(value=self.ALL)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=3)
        self.rowconfigure(3, weight=2)

        header = ttk.Frame(self)
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text="Simulation History", style="H1.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Button(header, text="Load sample data", command=self.load_samples).grid(row=0, column=1, padx=(0, 6))
        ttk.Button(header, text="Export CSV...", command=self.export_csv).grid(row=0, column=2)

        bar = ttk.Frame(self)
        bar.grid(row=1, column=0, sticky="ew", pady=(10, 8))
        ttk.Label(bar, text="Filter:", style="Muted.TLabel").pack(side="left", padx=(0, 6))
        box = ttk.Combobox(bar, textvariable=self.filter_var, state="readonly", width=16,
                           values=[self.ALL] + [n for n in self.app.algorithm_names()])
        box.pack(side="left", padx=(0, 12))
        box.bind("<<ComboboxSelected>>", lambda _e: self.refresh())
        ttk.Button(bar, text="Load selected into Analytics", style="Accent.TButton", command=self.load_selected).pack(side="left", padx=(0, 6))
        ttk.Button(bar, text="Delete selected", style="Danger.TButton", command=self.delete_selected).pack(side="left", padx=(0, 6))
        ttk.Button(bar, text="Clear all", style="Danger.TButton", command=self.clear_all).pack(side="left", padx=(0, 6))
        ttk.Button(bar, text="Refresh", command=self.refresh).pack(side="left")
        self.count_label = ttk.Label(bar, text="", style="Muted.TLabel")
        self.count_label.pack(side="right")

        cols = [("id", "ID", 50, "center"), ("date", "Date", 140, "center"), ("alg", "Algorithm", 100, "w"),
                ("n", "Customers", 80, "center"), ("c", "Counters", 70, "center"), ("seed", "Seed", 90, "center"),
                ("wait", "Avg wait", 80, "center"), ("tat", "Avg turnaround", 100, "center"),
                ("maxq", "Max queue", 80, "center"), ("util", "Util %", 70, "center"), ("group", "Group", 110, "center")]
        self.table = DataTable(self, cols, height=10, selectmode="extended")
        self.table.grid(row=2, column=0, sticky="nsew")
        self.chart = ChartTab(self, charts.draw_history, figsize=(9, 3))
        self.chart.grid(row=3, column=0, sticky="nsew", pady=(12, 0))
        self.refresh()

    def _filter_key(self):
        name = self.filter_var.get()
        for cls_name, key in self.app.algorithm_keys().items():
            if cls_name == name:
                return key
        return None

    def refresh(self) -> None:
        try:
            df = self.app.db.get_history(self._filter_key())
            everything = self.app.db.get_history() if self._filter_key() else df
        except PilaError as exc:
            messagebox.showerror("Database error", str(exc), parent=self)
            return
        self.table.clear()
        for r in df.itertuples(index=False):
            seed = "" if r.seed is None or r.seed != r.seed else int(r.seed)
            self.table.add((r.id, r.created_at.replace("T", " "), r.algorithm_name, r.num_customers, r.num_counters,
                            seed, f"{r.avg_waiting_time:.2f}", f"{r.avg_turnaround_time:.2f}", r.max_queue_length,
                            f"{r.utilization * 100:.1f}", r.group_id), iid=str(r.id))
        self.count_label.configure(text=f"{len(df)} runs shown")
        self.chart.redraw(history_algorithm_averages(everything))

    def _selected_ids(self):
        return [int(i) for i in self.table.selected()]

    def load_selected(self) -> None:
        ids = self._selected_ids()
        if not ids:
            messagebox.showinfo("Load runs", "Select one or more runs first.", parent=self)
            return
        try:
            results = [self.app.db.load_result(i) for i in ids]
        except PilaError as exc:
            messagebox.showerror("Could not load run", str(exc), parent=self)
            return
        if len({r.group_id for r in results}) > 1 or len({r.algorithm_key for r in results}) != len(results):
            messagebox.showwarning(
                "Select one comparison",
                "To compare fairly, select at most one run per algorithm and only from the same Group.",
                parent=self)
            return
        self.app.register_results(results, goto_analytics=True, save=False, replace=True)

    def delete_selected(self) -> None:
        ids = self._selected_ids()
        if not ids:
            return
        if messagebox.askyesno("Delete runs", f"Delete {len(ids)} selected run(s)?", parent=self):
            try:
                self.app.db.delete_simulations(ids)
            except PilaError as exc:
                messagebox.showerror("Database error", str(exc), parent=self)
                return
            self.refresh()

    def clear_all(self) -> None:
        if messagebox.askyesno("Clear history", "Delete ALL saved simulation runs? Presets are kept.", parent=self):
            try:
                self.app.db.clear_history()
            except PilaError as exc:
                messagebox.showerror("Database error", str(exc), parent=self)
                return
            self.refresh()

    def export_csv(self) -> None:
        try:
            df = self.app.db.get_history()
        except PilaError as exc:
            messagebox.showerror("Database error", str(exc), parent=self)
            return
        if df.empty:
            messagebox.showinfo("Export", "History is empty - nothing to export.", parent=self)
            return
        path = filedialog.asksaveasfilename(parent=self, title="Export history", defaultextension=".csv",
                                            initialdir=self.app.data_dir(), initialfile="pila_history.csv",
                                            filetypes=[("CSV files", "*.csv")])
        if not path:
            return
        try:
            out = export_history_csv(df, path)
        except PilaError as exc:
            messagebox.showerror("Export failed", str(exc), parent=self)
            return
        self.app.status(f"Exported history to {out}")

    def load_samples(self) -> None:
        try:
            saved = seed_sample_history(self.app.db)
        except PilaError as exc:
            messagebox.showerror("Could not load sample data", str(exc), parent=self)
            return
        self.refresh()
        self.app.simulation_page.refresh_presets()
        self.app.status(f"Added {saved} sample runs and 4 presets (Bank Branch, Hospital Triage, ...).")
