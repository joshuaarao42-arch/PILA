"""Animated real-time queue visualisation (Pygame).

The visualiser is a *view* over :class:`pila.engine.SimulationEngine`: every
frame it advances the engine's clock by ``dt * speed`` and draws the result.
Customers glide between the arrivals lane, the waiting queue, the counters and
the exit, so you can literally watch a scheduling algorithm make its choices.

Controls: SPACE pause - UP/DOWN faster/slower - R restart - ESC quit.

It is designed to run in its own process (see :func:`run_live_simulation`) so
it never fights Tkinter for the main loop.
"""
from __future__ import annotations

import math
import os
import queue as queue_module
from typing import Dict, List, Optional, Sequence, Tuple

from .algorithms import create_algorithm
from .engine import SimulationEngine
from .models import Customer, CustomerState, SimulationConfig
from .theme import COLORS, PRIORITY_COLORS, hex_to_rgb

WIDTH, HEIGHT = 1280, 780
HEADER_H = 64
STRIP_RECT = (20, 76, 1240, 62)
QUEUE_RECT = (20, 150, 600, 404)
COUNTER_RECT = (640, 150, 620, 404)
STATS_Y = 568

STRIP_X0, STRIP_STEP, STRIP_VISIBLE = 150, 38, 28
SLOT_W, SLOT_H = 52, 58
NODE_X, BAR_X0, BAR_X1, EXIT_X = 775, 820, 1085, 1205

MIN_SPEED, MAX_SPEED = 0.1, 200.0

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")


def _rgb(name: str) -> Tuple[int, int, int]:
    return hex_to_rgb(COLORS[name])


def _blend(a: Tuple[int, int, int], b: Tuple[int, int, int], t: float) -> Tuple[int, int, int]:
    t = max(0.0, min(1.0, t))
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))  # type: ignore[return-value]


class _Visual:
    """Smoothed on-screen state of one customer."""

    __slots__ = ("x", "y", "r", "done_seen")

    def __init__(self, x: float, y: float, r: float) -> None:
        self.x, self.y, self.r = x, y, r
        self.done_seen: Optional[float] = None


class QueueVisualizer:
    def __init__(
        self,
        customers: Sequence[Customer],
        config: SimulationConfig,
        algorithm_key: str,
        speed: Optional[float] = None,
        cmd_queue=None,
        out_queue=None,
        headless: bool = False,
    ) -> None:
        self.customers = list(customers)
        self.config = config
        self.algorithm_key = algorithm_key
        self.speed = max(MIN_SPEED, min(MAX_SPEED, speed if speed is not None else config.speed))
        self.cmd_queue = cmd_queue
        self.out_queue = out_queue
        self.headless = headless
        self.paused = False
        self.result = None
        self._result_sent = False
        self._real_time = 0.0
        self._buttons: List[Tuple[str, Tuple[int, int, int, int]]] = []
        self.screen = None
        self.pg = None
        self._reset()

    # ----------------------------------------------------------------- set-up
    def _reset(self) -> None:
        algo = create_algorithm(self.algorithm_key, self.config.time_quantum)
        self.engine = SimulationEngine(self.customers, self.config.num_counters, algo)
        self.visuals: Dict[int, _Visual] = {
            c.id: _Visual(WIDTH + 60, STRIP_RECT[1] + STRIP_RECT[3] / 2, 11) for c in self.engine.customers
        }
        avg_service = sum(c.service_time for c in self.customers) / len(self.customers)
        self._heat_scale = max(20.0, avg_service * 6)
        self.result = None
        self.paused = False

    def _setup_pygame(self) -> None:
        if self.headless:
            os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        try:
            import pygame
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("Pygame is not installed. Run: pip install pygame") from exc
        self.pg = pygame
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption(f"PILA - Live Simulation - {self.engine.algorithm.name}")
        names = "segoeui,inter,helveticaneue,ubuntu,arial,dejavusans"
        sysfont = pygame.font.SysFont
        self.fonts = {
            "title": sysfont(names, 28, bold=True),
            "h1": sysfont(names, 17, bold=True),
            "body": sysfont(names, 14),
            "bold": sysfont(names, 14, bold=True),
            "small": sysfont(names, 12),
            "tiny": sysfont(names, 11),
            "big": sysfont(names, 26, bold=True),
            "node": sysfont(names, 13, bold=True),
            "node_s": sysfont(names, 10, bold=True),
        }
        self.clock = pygame.time.Clock()

    # ---------------------------------------------------------------- layout
    def _row_geometry(self, counter_id: int) -> Tuple[float, float]:
        n = len(self.engine.counters)
        top = COUNTER_RECT[1] + 44
        avail = COUNTER_RECT[3] - 44 - 10
        row_h = min(78.0, avail / n)
        return top + (counter_id - 1) * row_h + row_h / 2, row_h

    def _queue_slot(self, index: int) -> Tuple[float, float, bool]:
        cols = (QUEUE_RECT[2] - 24) // SLOT_W
        rows = (QUEUE_RECT[3] - 52) // SLOT_H
        if index >= cols * rows:
            index = cols * rows - 1
            visible = False
        else:
            visible = True
        col, row = index % cols, index // cols
        x = QUEUE_RECT[0] + 14 + col * SLOT_W + SLOT_W / 2
        y = QUEUE_RECT[1] + 48 + row * SLOT_H + 24
        return x, y, visible

    def _targets(self) -> Dict[int, Tuple[float, float, float, bool]]:
        eng = self.engine
        out: Dict[int, Tuple[float, float, float, bool]] = {}
        strip_y = STRIP_RECT[1] + STRIP_RECT[3] / 2
        i = 0
        for c in eng.customers:
            if c.state is CustomerState.UPCOMING:
                if i < STRIP_VISIBLE:
                    out[c.id] = (STRIP_X0 + i * STRIP_STEP, strip_y, 11, True)
                else:
                    out[c.id] = (WIDTH + 60, strip_y, 11, False)
                i += 1
        for j, c in enumerate(eng.waiting_in_order()):
            x, y, vis = self._queue_slot(j)
            out[c.id] = (x, y, 17, vis)
        for ctr in eng.counters:
            if ctr.customer is not None:
                y, row_h = self._row_geometry(ctr.id)
                out[ctr.customer.id] = (NODE_X, y, max(9, min(19, row_h / 2 - 5)), True)
        for c in eng.completed:
            y, row_h = self._row_geometry(c.counter_id)
            out[c.id] = (EXIT_X, y, max(9, min(19, row_h / 2 - 5)), True)
        return out

    # --------------------------------------------------------------- updating
    def _advance_sim(self, dt: float) -> None:
        eng = self.engine
        if self.paused or eng.finished:
            return
        eng.advance_to(eng.now + dt * self.speed)
        if eng.finished and self.result is None:
            self.result = eng.result(self.config)
            if self.out_queue is not None and not self._result_sent:
                self._result_sent = True
                self.out_queue.put(("finished", self.result))

    def _animate(self, dt: float) -> None:
        k = min(1.0, dt * 9.0)
        for c_id, (tx, ty, tr, _vis) in self._targets().items():
            v = self.visuals[c_id]
            v.x += (tx - v.x) * k
            v.y += (ty - v.y) * k
            v.r += (tr - v.r) * k
        for c in self.engine.completed:
            v = self.visuals[c.id]
            if v.done_seen is None:
                v.done_seen = self._real_time

    def _update(self, dt: float) -> None:
        self._real_time += dt
        self._advance_sim(dt)
        self._animate(dt)

    # ----------------------------------------------------------------- events
    def _set_speed(self, value: float) -> None:
        self.speed = max(MIN_SPEED, min(MAX_SPEED, value))

    def _action(self, name: str) -> None:
        if name == "pause":
            self.paused = not self.paused
        elif name == "faster":
            self._set_speed(self.speed * 2)
        elif name == "slower":
            self._set_speed(self.speed / 2)
        elif name == "restart":
            self._reset()

    def _handle_events(self) -> bool:
        pg = self.pg
        for event in pg.event.get():
            if event.type == pg.QUIT:
                return False
            if event.type == pg.KEYDOWN:
                if event.key == pg.K_ESCAPE:
                    return False
                if event.key == pg.K_SPACE:
                    self._action("pause")
                elif event.key in (pg.K_UP, pg.K_RIGHT, pg.K_PLUS, pg.K_EQUALS):
                    self._action("faster")
                elif event.key in (pg.K_DOWN, pg.K_LEFT, pg.K_MINUS):
                    self._action("slower")
                elif event.key == pg.K_r:
                    self._action("restart")
            elif event.type == pg.MOUSEBUTTONDOWN and event.button == 1:
                for name, (x, y, w, h) in self._buttons:
                    if x <= event.pos[0] <= x + w and y <= event.pos[1] <= y + h:
                        self._action(name)
        return True

    def _poll_commands(self) -> bool:
        if self.cmd_queue is None:
            return True
        while True:
            try:
                cmd, value = self.cmd_queue.get_nowait()
            except queue_module.Empty:
                return True
            if cmd == "stop":
                return False
            if cmd == "speed":
                self._set_speed(float(value))
            elif cmd == "toggle_pause":
                self._action("pause")
            elif cmd == "restart":
                self._action("restart")

    # ---------------------------------------------------------------- drawing
    def _text(self, text, font, color, pos, anchor="topleft"):
        surf = self.fonts[font].render(text, True, color)
        rect = surf.get_rect(**{anchor: pos})
        self.screen.blit(surf, rect)
        return rect

    def _fit(self, text: str, font: str, max_w: int) -> str:
        f = self.fonts[font]
        if f.size(text)[0] <= max_w:
            return text
        while text and f.size(text + "...")[0] > max_w:
            text = text[:-1]
        return text + "..."

    def _panel(self, rect, title: str, subtitle: str = "") -> None:
        pg = self.pg
        pg.draw.rect(self.screen, _rgb("surface"), rect, border_radius=12)
        pg.draw.rect(self.screen, _rgb("border"), rect, width=1, border_radius=12)
        r = self._text(title, "h1", _rgb("text"), (rect[0] + 16, rect[1] + 10))
        if subtitle:
            self._text(subtitle, "small", _rgb("muted"), (r.right + 10, rect[1] + 14))

    def _alpha_circle(self, x, y, radius, color, alpha) -> None:
        size = int(radius * 2 + 4)
        surf = self.pg.Surface((size, size), self.pg.SRCALPHA)
        self.pg.draw.circle(surf, (*color, int(alpha)), (size // 2, size // 2), int(radius))
        self.screen.blit(surf, (x - size // 2, y - size // 2))

    def _node_color(self, c: Customer) -> Tuple[int, int, int]:
        if c.state is CustomerState.SERVING:
            return _rgb("green")
        if c.state is CustomerState.DONE:
            return _rgb("lavender")
        if c.state is CustomerState.WAITING:
            if c.has_started:  # preempted and sent back (Round Robin)
                return _rgb("purple")
            heat = (self.engine.now - c.arrival_time) / self._heat_scale
            return _blend(_rgb("amber"), _rgb("red"), heat)
        return _rgb("surface2")

    def _draw_node(self, c: Customer, v: _Visual, alpha: float = 1.0) -> None:
        pg, r = self.pg, max(6, int(v.r))
        x, y = int(v.x), int(v.y)
        ring = hex_to_rgb(PRIORITY_COLORS[min(c.priority, 5) - 1])
        fill = self._node_color(c)
        if c.state is CustomerState.SERVING:
            pulse = 0.5 + 0.5 * math.sin(self._real_time * 5)
            self._alpha_circle(x, y, r + 5 + 3 * pulse, _rgb("green"), 55)
        if c.state is CustomerState.UPCOMING:
            pg.draw.circle(self.screen, _rgb("bg"), (x, y), r)
            pg.draw.circle(self.screen, ring, (x, y), r, 2)
            label_color = _rgb("muted")
        elif alpha >= 0.98:
            pg.draw.circle(self.screen, fill, (x, y), r)
            pg.draw.circle(self.screen, ring, (x, y), r, 3)
            label_color = _rgb("bg")
        else:
            self._alpha_circle(x, y, r, fill, 255 * alpha)
            label_color = _rgb("bg")
        font = "node" if r >= 14 else "node_s"
        self._text(str(c.id), font, label_color, (x, y), "center")

    def _draw_header(self) -> None:
        pg, eng = self.pg, self.engine
        pg.draw.rect(self.screen, _rgb("surface"), (0, 0, WIDTH, HEADER_H))
        pg.draw.line(self.screen, _rgb("border"), (0, HEADER_H), (WIDTH, HEADER_H))
        self._text("PILA", "title", _rgb("accent"), (20, 14))
        self._text(eng.algorithm.name, "h1", _rgb("amber"), (112, 10))
        self._text(self._fit(eng.algorithm.description, "small", 640), "small", _rgb("muted"), (112, 36))
        state = "FINISHED" if eng.finished else ("PAUSED" if self.paused else "RUNNING")
        color = _rgb("green") if state == "RUNNING" else (_rgb("accent") if state == "FINISHED" else _rgb("amber"))
        self._text(state, "bold", color, (780, 14))
        self._text(f"Speed {self.speed:g}x", "small", _rgb("muted"), (780, 36))

        self._buttons = []
        labels = [("pause", "Resume" if self.paused else "Pause"), ("slower", "Slower"),
                  ("faster", "Faster"), ("restart", "Restart")]
        x = WIDTH - 20 - len(labels) * 92 - (len(labels) - 1) * 8
        mouse = pg.mouse.get_pos()
        for name, label in labels:
            rect = (x, 15, 92, 34)
            hover = rect[0] <= mouse[0] <= rect[0] + rect[2] and rect[1] <= mouse[1] <= rect[1] + rect[3]
            pg.draw.rect(self.screen, _rgb("border") if hover else _rgb("surface2"), rect, border_radius=8)
            pg.draw.rect(self.screen, _rgb("border"), rect, width=1, border_radius=8)
            self._text(label, "bold", _rgb("text"), (x + 46, 32), "center")
            self._buttons.append((name, rect))
            x += 100

    def _draw_strip(self) -> None:
        self._panel(STRIP_RECT, "Arrivals", "")
        self._text("UPCOMING", "tiny", _rgb("muted"), (STRIP_RECT[0] + 16, STRIP_RECT[1] + 38))
        remaining = sum(1 for c in self.engine.customers if c.state is CustomerState.UPCOMING)
        if remaining > STRIP_VISIBLE:
            self._text(f"+{remaining - STRIP_VISIBLE} more", "small", _rgb("muted"),
                       (STRIP_RECT[0] + STRIP_RECT[2] - 16, STRIP_RECT[1] + STRIP_RECT[3] / 2), "midright")

    def _draw_queue_panel(self) -> None:
        eng = self.engine
        self._panel(QUEUE_RECT, "Waiting queue", "next to be served: top-left")
        self._text(f"{len(eng.queue)} waiting", "bold", _rgb("amber"),
                   (QUEUE_RECT[0] + QUEUE_RECT[2] - 16, QUEUE_RECT[1] + 12), "topright")
        cols = (QUEUE_RECT[2] - 24) // SLOT_W
        rows = (QUEUE_RECT[3] - 52) // SLOT_H
        capacity = cols * rows
        for j in range(min(len(eng.queue), capacity)):
            x, y, _ = self._queue_slot(j)
            self.pg.draw.rect(self.screen, _rgb("surface2"), (x - SLOT_W / 2 + 3, y - 24, SLOT_W - 6, SLOT_H - 6),
                              border_radius=8)
        if len(eng.queue) > capacity:
            self._text(f"+{len(eng.queue) - capacity} more waiting", "small", _rgb("muted"),
                       (QUEUE_RECT[0] + QUEUE_RECT[2] / 2, QUEUE_RECT[1] + QUEUE_RECT[3] - 12), "center")
        if not eng.queue and not eng.finished:
            self._text("Queue is empty", "body", _rgb("muted"),
                       (QUEUE_RECT[0] + QUEUE_RECT[2] / 2, QUEUE_RECT[1] + QUEUE_RECT[3] / 2), "center")

    def _draw_counters(self) -> None:
        pg, eng = self.pg, self.engine
        self._panel(COUNTER_RECT, "Service counters", f"{len(eng.counters)} open")
        self._text("progress", "tiny", _rgb("muted"), (BAR_X0, COUNTER_RECT[1] + 30))
        self._text("exit", "tiny", _rgb("muted"), (EXIT_X, COUNTER_RECT[1] + 30), "midtop")
        for ctr in eng.counters:
            cy, row_h = self._row_geometry(ctr.id)
            rect = (COUNTER_RECT[0] + 10, cy - row_h / 2 + 3, COUNTER_RECT[2] - 20, row_h - 6)
            pg.draw.rect(self.screen, _rgb("surface2"), rect, border_radius=10)
            busy = ctr.customer is not None
            pg.draw.circle(self.screen, _rgb("green") if busy else _rgb("lavender"), (int(rect[0] + 16), int(cy)), 5)
            self._text(f"Counter {ctr.id}", "bold", _rgb("text"), (rect[0] + 30, cy - 10 if row_h >= 44 else cy), "midleft" if row_h < 44 else "topleft")
            if row_h >= 44:
                self._text(f"served {ctr.customers_served}", "tiny", _rgb("muted"), (rect[0] + 30, cy + 8))
            bar = (BAR_X0, cy - 7, BAR_X1 - BAR_X0, 14)
            pg.draw.rect(self.screen, _rgb("bg"), bar, border_radius=7)
            c = ctr.customer
            if c is not None:
                remaining = eng.remaining_of(c)
                done_frac = 1 - remaining / c.service_time
                pg.draw.rect(self.screen, _rgb("green"), (bar[0], bar[1], max(4, bar[2] * done_frac), bar[3]), border_radius=7)
                if eng.algorithm.preemptive:
                    slice_len = ctr.slice_end - ctr.slice_start
                    stop = 1 - (c.remaining_time - slice_len) / c.service_time
                    if stop < 0.999:
                        sx = bar[0] + bar[2] * stop
                        pg.draw.line(self.screen, _rgb("purple"), (sx, bar[1] - 3), (sx, bar[1] + bar[3] + 3), 2)
                self._text(f"#{c.id}  {remaining:.1f} left  (P{c.priority})", "tiny", _rgb("muted"), (BAR_X0, cy + 10))
            else:
                self._text("idle", "tiny", _rgb("muted"), (BAR_X0, cy + 10))

    def _draw_stats(self) -> None:
        pg, eng = self.pg, self.engine
        s = eng.live_stats()
        cards = [
            ("Simulation time", f"{s['now']:.1f}", "accent"),
            ("Waiting now", f"{int(s['queue_length'])}", "amber"),
            ("Max queue length", f"{int(s['max_queue_length'])}", "red"),
            ("Customers served", f"{int(s['served'])} / {int(s['total'])}", "green"),
            ("Avg wait (finished)", f"{s['avg_waiting']:.2f}", "purple"),
            ("Utilization", f"{s['utilization'] * 100:.0f}%", "accent"),
        ]
        cw, ch, gap = 244, 92, 12
        for i, (label, value, color) in enumerate(cards):
            x = 20 + (i % 3) * (cw + gap)
            y = STATS_Y + (i // 3) * (ch + gap)
            pg.draw.rect(self.screen, _rgb("surface"), (x, y, cw, ch), border_radius=12)
            pg.draw.rect(self.screen, _rgb("border"), (x, y, cw, ch), width=1, border_radius=12)
            pg.draw.rect(self.screen, _rgb(color), (x, y + 18, 4, ch - 36), border_radius=2)
            self._text(label, "small", _rgb("muted"), (x + 18, y + 14))
            self._text(value, "big", _rgb("text"), (x + 18, y + 38))

        # queue-length sparkline
        sx, sy, sw, sh = 796, STATS_Y, 464, 116
        pg.draw.rect(self.screen, _rgb("surface"), (sx, sy, sw, sh), border_radius=12)
        pg.draw.rect(self.screen, _rgb("border"), (sx, sy, sw, sh), width=1, border_radius=12)
        self._text("Queue length over time", "small", _rgb("muted"), (sx + 16, sy + 10))
        px, py, pw, ph = sx + 16, sy + 32, sw - 32, sh - 46
        pts = list(eng.queue_timeline) + [(eng.now, len(eng.queue))]
        tmax = max(eng.now, 10.0)
        qmax = max(5, eng.max_queue_length)
        poly: List[Tuple[float, float]] = []
        prev_q = 0
        for t, q in pts:
            x = px + pw * min(t / tmax, 1.0)
            poly.append((x, py + ph - ph * prev_q / qmax))
            poly.append((x, py + ph - ph * q / qmax))
            prev_q = q
        pg.draw.line(self.screen, _rgb("border"), (px, py + ph), (px + pw, py + ph))
        if len(poly) > 1:
            pg.draw.lines(self.screen, _rgb("amber"), False, poly, 2)
        self._text(f"{qmax}", "tiny", _rgb("muted"), (px - 4, py), "topright")

        # legend
        ly = sy + sh + 10
        pg.draw.rect(self.screen, _rgb("surface"), (sx, ly, sw, 82), border_radius=12)
        pg.draw.rect(self.screen, _rgb("border"), (sx, ly, sw, 82), width=1, border_radius=12)
        states = [("Upcoming", _rgb("bg")), ("Waiting (redder = longer)", _rgb("amber")),
                  ("Returned (RR)", _rgb("purple")), ("Serving", _rgb("green")), ("Done", _rgb("lavender"))]
        x = sx + 16
        for i, (label, col) in enumerate(states):
            row_y = ly + 16 + (i // 3) * 22
            col_x = sx + 16 + (i % 3) * 150
            pg.draw.circle(self.screen, col, (col_x + 6, row_y + 7), 6)
            if col == _rgb("bg"):
                pg.draw.circle(self.screen, _rgb("muted"), (col_x + 6, row_y + 7), 6, 1)
            self._text(label, "tiny", _rgb("text"), (col_x + 18, row_y))
        self._text("Ring colour = priority:", "tiny", _rgb("muted"), (sx + 16, ly + 60))
        levels = self.config.priority_levels
        for p in range(1, levels + 1):
            cx = sx + 150 + (p - 1) * 46
            pg.draw.circle(self.screen, hex_to_rgb(PRIORITY_COLORS[p - 1]), (cx, ly + 67), 6)
            self._text(f"P{p}", "tiny", _rgb("text"), (cx + 10, ly + 60))

    def _draw_finished_banner(self) -> None:
        if self.result is None:
            return
        s = self.result.summary
        w, h = 520, 190
        x, y = QUEUE_RECT[0] + (QUEUE_RECT[2] - w) // 2, 250
        overlay = self.pg.Surface((w, h), self.pg.SRCALPHA)
        self.pg.draw.rect(overlay, (*_rgb("bg"), 235), (0, 0, w, h), border_radius=16)
        self.pg.draw.rect(overlay, (*_rgb("accent"), 255), (0, 0, w, h), width=2, border_radius=16)
        self.screen.blit(overlay, (x, y))
        self._text("SIMULATION COMPLETE", "h1", _rgb("accent"), (x + w / 2, y + 20), "midtop")
        lines = [f"Avg waiting time:  {s.avg_waiting_time:.2f}", f"Avg turnaround:  {s.avg_turnaround_time:.2f}",
                 f"Max queue length:  {s.max_queue_length}", f"Utilization:  {s.utilization * 100:.1f}%"]
        for i, line in enumerate(lines):
            self._text(line, "body", _rgb("text"), (x + w / 2, y + 56 + i * 24), "midtop")
        self._text("R = replay    ESC = close window", "small", _rgb("muted"), (x + w / 2, y + h - 28), "midtop")

    def _draw(self) -> None:
        self.screen.fill(_rgb("bg"))
        self._draw_header()
        self._draw_strip()
        self._draw_queue_panel()
        self._draw_counters()
        eng = self.engine
        for c in eng.customers:
            v = self.visuals[c.id]
            if c.state is CustomerState.UPCOMING and v.x > WIDTH:
                continue
            alpha = 1.0
            if c.state is CustomerState.DONE and v.done_seen is not None:
                alpha = 1.0 - max(0.0, min(1.0, (self._real_time - v.done_seen - 1.0) / 1.0))
                if alpha <= 0.02:
                    continue
            if c.state is CustomerState.WAITING:
                target = self._targets().get(c.id)
                if target is not None and not target[3]:
                    continue
            self._draw_node(c, v, alpha)
        self._draw_stats()
        self._draw_finished_banner()

    # ------------------------------------------------------------------- run
    def run(self) -> None:
        self._setup_pygame()
        running = True
        while running:
            dt = min(self.clock.tick(60) / 1000.0, 0.1)
            running = self._handle_events() and self._poll_commands()
            self._update(dt)
            self._draw()
            self.pg.display.flip()
        self.pg.quit()
        if self.out_queue is not None:
            self.out_queue.put(("closed", None))

    def snapshot(self, path: str, at_time: float) -> None:
        """Render a single frame (used for README screenshots / tests)."""
        self.headless = True
        self._setup_pygame()
        frame = 1 / 30
        while self.engine.now < at_time and not self.engine.finished:
            self._real_time += frame
            self.engine.advance_to(min(at_time, self.engine.now + 0.25))
            self._animate(frame)
        if self.engine.finished and self.result is None:
            self.result = self.engine.result(self.config)
        for _ in range(90):
            self._real_time += frame
            self._animate(frame)
        self._draw()
        self.pg.image.save(self.screen, path)
        self.pg.quit()


def run_live_simulation(customer_rows, config_dict, algorithm_key, speed, cmd_queue, out_queue) -> None:
    """Process entry point: build everything from plain data and run the window."""
    try:
        customers = [Customer(int(i), float(a), float(s), int(p)) for i, a, s, p in customer_rows]
        config = SimulationConfig.from_dict(config_dict)
        QueueVisualizer(customers, config, algorithm_key, speed, cmd_queue, out_queue).run()
    except Exception as exc:  # report to the parent instead of dying silently
        out_queue.put(("error", f"{type(exc).__name__}: {exc}"))


def main() -> None:  # pragma: no cover - manual demo
    import argparse
    from .generator import generate_customers

    parser = argparse.ArgumentParser(description="Standalone PILA live simulation window")
    parser.add_argument("--algorithm", default="fcfs", choices=["fcfs", "priority", "sjf", "rr"])
    parser.add_argument("--customers", type=int, default=40)
    parser.add_argument("--counters", type=int, default=3)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--speed", type=float, default=4.0)
    args = parser.parse_args()
    cfg = SimulationConfig(num_customers=args.customers, num_counters=args.counters, seed=args.seed,
                           speed=args.speed).validate()
    QueueVisualizer(generate_customers(cfg), cfg, args.algorithm).run()


if __name__ == "__main__":  # pragma: no cover
    main()
