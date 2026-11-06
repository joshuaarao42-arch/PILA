"""Matplotlib chart builders. Pure functions: ``(Figure, data) -> None``.

They never import Tkinter, so they can be unit-tested and used headless
(e.g. to generate the README images).
"""
from __future__ import annotations

from typing import Sequence

import numpy as np
import pandas as pd
from matplotlib.figure import Figure

from ..analytics import waiting_by_priority
from ..metrics import SimulationResult
from ..theme import ALGO_COLORS, COLORS, PRIORITY_COLORS, priority_color


def new_figure(figsize=(8, 5)) -> Figure:
    fig = Figure(figsize=figsize, dpi=100, facecolor=COLORS["surface"])
    fig.set_layout_engine("constrained")
    return fig


def _style(ax, title: str = "", xlabel: str = "", ylabel: str = "") -> None:
    ax.set_facecolor(COLORS["surface"])
    for spine in ax.spines.values():
        spine.set_color(COLORS["border"])
    ax.tick_params(colors=COLORS["muted"], labelsize=8)
    ax.set_title(title, color=COLORS["text"], fontsize=10, fontweight="bold", loc="left")
    ax.set_xlabel(xlabel, color=COLORS["muted"], fontsize=8)
    ax.set_ylabel(ylabel, color=COLORS["muted"], fontsize=8)
    ax.grid(True, axis="y", color=COLORS["border"], linewidth=0.5, alpha=0.7)
    ax.set_axisbelow(True)


def _placeholder(fig: Figure, text: str) -> None:
    fig.clear()
    ax = fig.add_subplot(111)
    ax.set_facecolor(COLORS["surface"])
    ax.axis("off")
    ax.text(0.5, 0.5, text, ha="center", va="center", color=COLORS["muted"], fontsize=12,
            transform=ax.transAxes)


def _color(result: SimulationResult) -> str:
    return ALGO_COLORS.get(result.algorithm_key, COLORS["accent"])


# ------------------------------------------------------------------ comparison
def draw_comparison(fig: Figure, results: Sequence[SimulationResult]) -> None:
    if not results:
        return _placeholder(fig, "Run a simulation to see algorithm comparisons")
    fig.clear()
    panels = [
        ("Average waiting time", lambda s: s.avg_waiting_time, True, "time units"),
        ("Average turnaround time", lambda s: s.avg_turnaround_time, True, "time units"),
        ("Maximum queue length", lambda s: s.max_queue_length, True, "customers"),
        ("Counter utilization", lambda s: s.utilization * 100, False, "%"),
    ]
    axes = fig.subplots(2, 2).ravel()
    names = [r.algorithm_name for r in results]
    colors = [_color(r) for r in results]
    for ax, (title, getter, lower_better, unit) in zip(axes, panels):
        values = [getter(r.summary) for r in results]
        bars = ax.bar(names, values, color=colors, width=0.62, edgecolor=COLORS["surface"])
        _style(ax, title, ylabel=unit)
        top = max(values) if max(values) > 0 else 1
        ax.set_ylim(0, top * 1.22)
        best = (min if lower_better else max)(values)
        for bar, v in zip(bars, values):
            is_best = lower_better and len(results) > 1 and v == best
            ax.text(bar.get_x() + bar.get_width() / 2, v + top * 0.02,
                    f"{v:.1f}" if title != "Maximum queue length" else f"{int(v)}",
                    ha="center", va="bottom", fontsize=8, fontweight="bold" if is_best else "normal",
                    color=COLORS["green"] if is_best else COLORS["text"])
            if is_best:
                bar.set_edgecolor(COLORS["green"])
                bar.set_linewidth(2)
        ax.tick_params(axis="x", labelsize=8)
    fig.suptitle("Algorithm comparison (green outline = best)", color=COLORS["muted"], fontsize=9)


# --------------------------------------------------------------- wait analysis
def draw_wait_analysis(fig: Figure, results: Sequence[SimulationResult]) -> None:
    if not results:
        return _placeholder(fig, "No data yet")
    fig.clear()
    ax1, ax2 = fig.subplots(1, 2)

    data = [[r.waiting_time for r in res.records] for res in results]
    box = ax1.boxplot(data, patch_artist=True, widths=0.55, showmeans=True,
                      medianprops=dict(color=COLORS["text"], linewidth=1.5),
                      meanprops=dict(marker="D", markerfacecolor=COLORS["amber"], markeredgecolor=COLORS["bg"], markersize=5),
                      whiskerprops=dict(color=COLORS["muted"]), capprops=dict(color=COLORS["muted"]),
                      flierprops=dict(marker="o", markersize=3, markerfacecolor=COLORS["muted"], markeredgecolor="none"))
    for patch, res in zip(box["boxes"], results):
        patch.set_facecolor(_color(res))
        patch.set_alpha(0.75)
        patch.set_edgecolor(COLORS["text"])
    ax1.set_xticks(range(1, len(results) + 1))
    ax1.set_xticklabels([r.algorithm_name for r in results])
    _style(ax1, "Waiting-time distribution", ylabel="time units (diamond = mean)")

    pivot = waiting_by_priority(results)
    if pivot.empty:
        ax2.axis("off")
        return
    levels = list(pivot.index)
    width = 0.8 / max(len(results), 1)
    x = np.arange(len(levels))
    for i, res in enumerate(results):
        vals = pivot[res.algorithm_name].reindex(levels).fillna(0).to_numpy()
        ax2.bar(x + i * width - 0.4 + width / 2, vals, width, label=res.algorithm_name,
                color=_color(res), edgecolor=COLORS["surface"])
    ax2.set_xticks(x)
    ax2.set_xticklabels([f"P{int(p)}" for p in levels])
    _style(ax2, "Average wait by priority (P1 = most urgent)", ylabel="time units")
    legend = ax2.legend(fontsize=7, facecolor=COLORS["surface2"], edgecolor=COLORS["border"])
    for text in legend.get_texts():
        text.set_color(COLORS["text"])


# ---------------------------------------------------------------- queue length
def draw_queue_length(fig: Figure, results: Sequence[SimulationResult]) -> None:
    if not results:
        return _placeholder(fig, "No data yet")
    fig.clear()
    ax = fig.add_subplot(111)
    for res in results:
        t, q = zip(*res.queue_timeline)
        ax.step(t, q, where="post", label=f"{res.algorithm_name} (max {res.summary.max_queue_length})",
                color=_color(res), linewidth=1.6, alpha=0.9)
    _style(ax, "Queue length over time", "simulation time", "customers waiting")
    ax.set_ylim(bottom=0)
    legend = ax.legend(fontsize=8, facecolor=COLORS["surface2"], edgecolor=COLORS["border"])
    for text in legend.get_texts():
        text.set_color(COLORS["text"])


# ----------------------------------------------------------------------- gantt
def draw_gantt(fig: Figure, result: SimulationResult) -> None:
    if result is None:
        return _placeholder(fig, "Run a simulation to see the service timeline")
    fig.clear()
    ax = fig.add_subplot(111)
    counters = sorted({s.counter_id for s in result.slices})
    priority_of = {r.customer_id: r.priority for r in result.records}
    horizon = result.summary.makespan
    min_label_width = horizon * 0.022
    for s in result.slices:
        y = s.counter_id
        ax.broken_barh([(s.start, s.duration)], (y - 0.38, 0.76),
                       facecolors=priority_color(priority_of[s.customer_id]),
                       edgecolor=COLORS["surface"], linewidth=0.8)
        if s.duration >= min_label_width:
            ax.text(s.start + s.duration / 2, y, str(s.customer_id), ha="center", va="center",
                    fontsize=7, color=COLORS["bg"], fontweight="bold")
    ax.set_yticks(counters)
    ax.set_yticklabels([f"Counter {c}" for c in counters])
    ax.invert_yaxis()
    ax.set_xlim(0, horizon * 1.01)
    _style(ax, f"Service timeline - {result.algorithm_name} (labels are customer ids)", "simulation time")
    ax.grid(True, axis="x", color=COLORS["border"], linewidth=0.5, alpha=0.7)
    ax.grid(False, axis="y")
    from matplotlib.patches import Patch
    levels = sorted(set(priority_of.values()))
    handles = [Patch(facecolor=priority_color(p), label=f"P{p}") for p in levels]
    legend = ax.legend(handles=handles, fontsize=7, ncols=len(handles), loc="upper center",
                       bbox_to_anchor=(0.5, -0.12), facecolor=COLORS["surface2"], edgecolor=COLORS["border"],
                       title="priority", title_fontsize=7)
    legend.get_title().set_color(COLORS["muted"])
    for text in legend.get_texts():
        text.set_color(COLORS["text"])


# --------------------------------------------------------------------- history
def draw_history(fig: Figure, averages: pd.DataFrame) -> None:
    if averages is None or averages.empty:
        return _placeholder(fig, "No saved runs yet - run a simulation or load sample data")
    fig.clear()
    ax1, ax2 = fig.subplots(1, 2)
    names = list(averages["algorithm_name"])
    key_of = {"FCFS": "fcfs", "Priority": "priority", "SJF": "sjf", "Round Robin": "rr"}
    colors = [ALGO_COLORS.get(key_of.get(n, ""), COLORS["accent"]) for n in names]
    for ax, col, title in ((ax1, "avg_waiting_time", "Mean waiting time across saved runs"),
                           (ax2, "avg_turnaround_time", "Mean turnaround time across saved runs")):
        vals = averages[col].to_numpy()
        bars = ax.bar(names, vals, color=colors, width=0.6, edgecolor=COLORS["surface"])
        _style(ax, title, ylabel="time units")
        ax.set_ylim(0, max(vals.max(), 1) * 1.2)
        for bar, v, runs in zip(bars, vals, averages["runs"]):
            ax.text(bar.get_x() + bar.get_width() / 2, v, f"{v:.1f}\n({runs} runs)", ha="center",
                    va="bottom", fontsize=7, color=COLORS["text"])
