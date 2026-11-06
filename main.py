"""PILA entry point.

    python main.py                 # launch the desktop app
    python main.py --db my.db      # use a different SQLite file
    python main.py --seed-sample   # fill the database with demo runs and exit
"""
import argparse
import multiprocessing


def main() -> None:
    parser = argparse.ArgumentParser(description="PILA - Intelligent Queue Simulation & Optimization System")
    parser.add_argument("--db", help="path to the SQLite database (default: data/pila.db)")
    parser.add_argument("--seed-sample", action="store_true", help="add demo simulation history and exit")
    args = parser.parse_args()

    if args.seed_sample:
        from pila.database import Database
        from pila.sample_data import seed_sample_history

        saved = seed_sample_history(Database(args.db))
        print(f"Added {saved} sample runs and 4 presets.")
        return

    from pila.ui.app import run

    run(args.db)


if __name__ == "__main__":
    multiprocessing.freeze_support()  # needed for spawned processes on Windows / frozen builds
    main()
