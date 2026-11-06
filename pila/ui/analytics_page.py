"""Analytics dashboard: KPI cards, comparison charts, Gantt timeline, summary table."""
from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import List

from ..analytics import best_algorithms, export_reports, results_to_summary_df
from ..errors import PilaError
from ..metrics import SimulationResult
from ..theme import COLORS
from . import charts
from .widgets import ChartTab, DataTable, MetricCard
from .ctk_compat import ttk


class AnalyticsPage(ttk.Frame):
    def __init__(self, master, app) -> None:
        super().__init__(master)
        self.app = app
        self.detail_var = tk.StringVar()
        self.insight = tk.StringVar()
        self.columnconfigure(0, weight=1)
        self.rowconfigure(3, weight=1)

        header = ttk.Frame(self)
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text="Analytics Dashboard", style="H1.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(header, text="Detail for:", style="Muted.TLabel").grid(row=0, column=1, padx=(0, 6))
        self.detail_box = ttk.Combobox(header, textvariable=self.detail_var, state="readonly", width=14)
        self.detail_box.grid(row=0, column=2, padx=(0, 12))
        self.detail_box.bind("<<ComboboxSelected>>", lambda _e: self.refresh())
        ttk.Button(header, text="Export CSV report...", style="Accent.TButton", command=self.export_csv).grid(row=0, column=3, padx=(0, 6))
        ttk.Button(header, text="Save charts (PNG)...", command=self.save_charts).grid(row=0, column=4)

        cards = ttk.Frame(self)
        cards.grid(row=1, column=0, sticky="ew", pady=(12, 8))
        spec = [("wait", "Average waiting time", COLORS["amber"]), ("tat", "Average turnaround", COLORS["accent"]),
                ("maxq", "Maximum queue length", COLORS["red"]), ("served", "Customers served", COLORS["green"]),
                ("util", "Counter utilization", COLORS["purple"]), ("resp", "Average response", COLORS["pink"])]
        self.cards = {}
        for i, (key, title, color) in enumerate(spec):
            card = MetricCard(cards, title, color)
            card.grid(row=0, column=i, sticky="ew", padx=(0 if i == 0 else 8, 0))
            cards.columnconfigure(i, weight=1, uniform="cards")
            self.cards[key] = card

        ttk.Label(self, textvariable=self.insight, style="Insight.TLabel").grid(row=2, column=0, sticky="w", pady=(0, 8))

        self.notebook = ttk.Notebook(self)
        self.notebook.grid(row=3, column=0, sticky="nsew")
        self.tabs = {
            "Comparison": ChartTab(self.notebook, charts.draw_comparison),
            "Wait analysis": ChartTab(self.notebook, charts.draw_wait_analysis),
            "Queue length": ChartTab(self.notebook, charts.draw_queue_length),
            "Service timeline": ChartTab(self.notebook, charts.draw_gantt),
        }
        for name, tab in self.tabs.items():
            self.notebook.add(tab, text=name)
        self.table = DataTable(self.notebook, [("a", "-", 100, "center")], height=6)
        self.notebook.add(self.table, text="Summary table")
        self.refresh()

    # ---------------------------------------------------------------- helpers
    def _results(self) -> List[SimulationResult]:
        return self.app.ordered_results()

    def _detail_result(self, results: List[SimulationResult]):
        for r in results:
            if r.algorithm_name == self.detail_var.get():
                return r
        return results[0] if results else None

    # ---------------------------------------------------------------- refresh
    def refresh(self) -> None:
        results = self._results()
        names = [r.algorithm_name for r in results]
        self.detail_box.configure(values=names)
        if self.detail_var.get() not in names:
            self.detail_var.set(names[0] if names else "")
        detail = self._detail_result(results)

        if detail is None:
            for card in self.cards.values():
                card.set("-")
            self.insight.set("Run a simulation or compare all algorithms to see analytics here.")
        else:
            s = detail.summary
            self.cards["wait"].set(f"{s.avg_waiting_time:.2f}", f"max {s.max_waiting_time:.0f} - {detail.algorithm_name}")
            self.cards["tat"].set(f"{s.avg_turnaround_time:.2f}", "time units")
            self.cards["maxq"].set(str(s.max_queue_length), f"avg {s.avg_queue_length:.2f}")
            self.cards["served"].set(f"{s.total_served}", f"of {s.total_customers} customers")
            self.cards["util"].set(f"{s.utilization * 100:.1f}%", f"{detail.config.num_counters} counters")
            self.cards["resp"].set(f"{s.avg_response_time:.2f}", f"throughput {s.throughput:.2f}/unit")
            summary = results_to_summary_df(results)
            if len(results) > 1:
                best = best_algorithms(summary)
                self.insight.set(
                    f"Best average wait: {best['Avg Waiting'][0]} ({best['Avg Waiting'][1]:.2f})   |   "
                    f"Best turnaround: {best['Avg Turnaround'][0]} ({best['Avg Turnaround'][1]:.2f})   |   "
                    f"Shortest peak queue: {best['Max Queue'][0]} ({best['Max Queue'][1]:.0f})")
            else:
                self.insight.set("Tip: use 'Compare All Algorithms' to see them side by side on identical customers.")

        self.tabs["Comparison"].redraw(results)
        self.tabs["Wait analysis"].redraw(results)
        self.tabs["Queue length"].redraw(results)
        self.tabs["Service timeline"].redraw(detail)
        if results:
            self.table.load_dataframe(results_to_summary_df(results))
        else:
            self.table.clear()

    # ----------------------------------------------------------------- export
    def export_csv(self) -> None:
        results = self._results()
        if not results:
            messagebox.showinfo("Export", "Run a simulation first - there is nothing to export yet.", parent=self)
            return
        path = filedialog.asksaveasfilename(parent=self, title="Export report", defaultextension=".csv",
                                            initialdir=self.app.data_dir(), initialfile="pila_report.csv",
                                            filetypes=[("CSV files", "*.csv")])
        if not path:
            return
        try:
            summary, customers = export_reports(results, path)
        except PilaError as exc:
            messagebox.showerror("Export failed", str(exc), parent=self)
            return
        self.app.status(f"Exported {summary.name} and {customers.name}")
        messagebox.showinfo("Export complete", f"Summary:\n{summary}\n\nPer-customer details:\n{customers}", parent=self)

    def save_charts(self) -> None:
        if not self._results():
            messagebox.showinfo("Save charts", "Run a simulation first.", parent=self)
            return
        folder = filedialog.askdirectory(parent=self, title="Choose a folder for the PNG charts",
                                         initialdir=self.app.data_dir())
        if not folder:
            return
        try:
            for name, tab in self.tabs.items():
                tab.figure.savefig(Path(folder) / f"pila_{name.lower().replace(' ', '_')}.png",
                                   facecolor=tab.figure.get_facecolor(), dpi=150)
        except OSError as exc:
            messagebox.showerror("Save failed", str(exc), parent=self)
            return
        self.app.status(f"Saved {len(self.tabs)} charts to {folder}")
