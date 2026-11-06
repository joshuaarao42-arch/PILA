"""Regenerate the README images in docs/images/ (needs a display; use xvfb on servers).

    xvfb-run -a -s "-screen 0 1440x960x24" python scripts/make_screenshots.py
"""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
OUT = ROOT / "docs" / "images"
OUT.mkdir(parents=True, exist_ok=True)


def live_view() -> None:
    os.environ["SDL_VIDEODRIVER"] = "dummy"
    from pila.generator import generate_customers
    from pila.models import SimulationConfig
    from pila.visualization import QueueVisualizer

    cfg = SimulationConfig(num_customers=45, num_counters=3, seed=11, priority_levels=4,
                           mean_interarrival=1.6, time_quantum=4).validate()
    QueueVisualizer(generate_customers(cfg), cfg, "rr").snapshot(str(OUT / "live_simulation.png"), 40)


def tk_pages() -> None:
    from PIL import ImageGrab
    from pila.ui.app import PilaApp

    app = PilaApp(os.path.join(tempfile.mkdtemp(), "shots.db"))
    app.geometry("1400x900+0+0")
    app.history_page.load_samples()
    sp = app.simulation_page
    sp.apply_config(__import__("pila.sample_data", fromlist=["x"]).SCENARIOS["Bank Branch"])
    sp.compare_all()

    def grab(name: str) -> None:
        for _ in range(5):
            app.update_idletasks()
            app.update()
        ImageGrab.grab(bbox=(0, 0, 1400, 900)).save(OUT / name)

    app.show_page("simulation"); grab("ui_simulation.png")
    app.show_page("analytics"); grab("ui_analytics.png")
    app.analytics_page.notebook.select(app.analytics_page.tabs["Service timeline"]); grab("ui_timeline.png")
    app.show_page("history"); grab("ui_history.png")
    app.destroy()


if __name__ == "__main__":
    live_view()
    try:
        tk_pages()
    except Exception as exc:  # screenshots of the Tk window are optional
        print("Skipped Tk screenshots:", exc)
    print("Images written to", OUT)
