"""PILA CustomTkinter theme and the small native ttk theme still in use."""
import tkinter as tk
from tkinter import ttk

import customtkinter as ctk

from ..theme import COLORS

FONT = "Segoe UI"


def apply_theme(root: tk.Tk) -> None:
    c = COLORS
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    root.configure(fg_color=c["bg"])
    style = ttk.Style(root)
    style.theme_use("clam")
    # Native ttk is retained only for Treeview and Notebook controls.
    root.option_add("*TCombobox*Listbox.background", c["surface2"])
    root.option_add("*TCombobox*Listbox.foreground", c["text"])
    root.option_add("*TCombobox*Listbox.selectBackground", c["accent"])
    root.option_add("*TCombobox*Listbox.selectForeground", c["bg"])
    root.option_add("*TCombobox*Listbox.font", (FONT, 10))

    style.configure(".", background=c["bg"], foreground=c["text"], fieldbackground=c["surface2"],
                    bordercolor=c["border"], lightcolor=c["surface"], darkcolor=c["surface"],
                    troughcolor=c["surface2"], focuscolor=c["bg"], font=(FONT, 10))
    style.configure("TFrame", background=c["bg"])
    style.configure("Card.TFrame", background=c["surface"])
    style.configure("Side.TFrame", background=c["surface"])
    style.configure("TLabel", background=c["bg"], foreground=c["text"])
    style.configure("Card.TLabel", background=c["surface"], foreground=c["text"])
    style.configure("Muted.TLabel", background=c["bg"], foreground=c["muted"])
    style.configure("CardMuted.TLabel", background=c["surface"], foreground=c["muted"], font=(FONT, 9))
    style.configure("H1.TLabel", background=c["bg"], font=(FONT, 18, "bold"))
    style.configure("CardTitle.TLabel", background=c["surface"], font=(FONT, 12, "bold"))
    style.configure("CardValue.TLabel", background=c["surface"], font=(FONT, 20, "bold"))
    style.configure("Logo.TLabel", background=c["surface"], foreground=c["accent"], font=(FONT, 24, "bold"))
    style.configure("Insight.TLabel", background=c["bg"], foreground=c["amber"], font=(FONT, 10))
    style.configure("Status.TLabel", background=c["surface"], foreground=c["muted"], font=(FONT, 9))

    style.configure("TButton", background=c["surface2"], foreground=c["text"], bordercolor=c["border"],
                    padding=(12, 7), relief="flat", font=(FONT, 10))
    style.map("TButton", background=[("active", c["border"]), ("disabled", c["surface"])],
              foreground=[("disabled", c["muted"])])
    style.configure("Accent.TButton", background=c["accent"], foreground=c["bg"], font=(FONT, 10, "bold"),
                    bordercolor=c["accent"])
    style.map("Accent.TButton", background=[("active", c["accent"]), ("disabled", c["border"])])
    style.configure("Danger.TButton", background=c["surface2"], foreground=c["red"])
    style.map("Danger.TButton", background=[("active", c["border"])])
    style.configure("Nav.TButton", background=c["surface"], foreground=c["muted"], anchor="w",
                    padding=(18, 11), borderwidth=0, font=(FONT, 11))
    style.map("Nav.TButton", background=[("active", c["surface2"])], foreground=[("active", c["text"])])
    style.configure("NavActive.TButton", background=c["surface2"], foreground=c["accent"], anchor="w",
                    padding=(18, 11), borderwidth=0, font=(FONT, 11, "bold"))
    style.map("NavActive.TButton", background=[("active", c["surface2"])])

    style.configure("TEntry", fieldbackground=c["surface2"], foreground=c["text"], insertcolor=c["text"],
                    bordercolor=c["border"], padding=5)
    style.map("TEntry", bordercolor=[("focus", c["accent"])])
    style.configure("TCombobox", fieldbackground=c["surface2"], background=c["surface2"], foreground=c["text"],
                    arrowcolor=c["text"], bordercolor=c["border"], padding=5)
    style.map("TCombobox", fieldbackground=[("readonly", c["surface2"])], foreground=[("readonly", c["text"])],
              bordercolor=[("focus", c["accent"])])
    style.configure("TCheckbutton", background=c["surface"], foreground=c["text"])
    style.map("TCheckbutton", background=[("active", c["surface"])])
    style.configure("Horizontal.TScale", background=c["surface"], troughcolor=c["surface2"])

    style.configure("Treeview", background=c["surface"], fieldbackground=c["surface"], foreground=c["text"],
                    rowheight=26, borderwidth=0, font=(FONT, 10))
    style.configure("Treeview.Heading", background=c["surface2"], foreground=c["muted"], borderwidth=0,
                    padding=(6, 6), font=(FONT, 9, "bold"))
    style.map("Treeview", background=[("selected", c["accent"])], foreground=[("selected", c["bg"])])
    style.map("Treeview.Heading", background=[("active", c["border"])])

    style.configure("TNotebook", background=c["bg"], borderwidth=0, tabmargins=(0, 0, 0, 0),
                    bordercolor=c["border"], lightcolor=c["bg"], darkcolor=c["bg"])
    style.configure("TNotebook.Tab", background=c["surface"], foreground=c["muted"], padding=(18, 9),
                    borderwidth=0, bordercolor=c["border"], lightcolor=c["surface"], darkcolor=c["surface"],
                    font=(FONT, 10))
    style.map("TNotebook.Tab", background=[("selected", c["surface2"])], foreground=[("selected", c["text"])])
    style.configure("Vertical.TScrollbar", background=c["surface2"], troughcolor=c["surface"],
                    bordercolor=c["surface"], arrowcolor=c["muted"])
