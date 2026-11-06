"""Small CustomTkinter adapter used by PILA's existing page layouts.

CustomTkinter does not provide a Treeview or Notebook, so those two controls
remain native ttk widgets while the application chrome uses CustomTkinter.
"""
from __future__ import annotations

import tkinter.ttk as _ttk
from types import SimpleNamespace

import customtkinter as ctk

from ..theme import COLORS


def _style(kwargs):
    name = kwargs.pop("style", "")
    kwargs.pop("padding", None)
    if name in {"Card.TFrame", "Side.TFrame"}:
        kwargs.setdefault("fg_color", COLORS["surface"])
        kwargs.setdefault("corner_radius", 14)
    elif name == "CardMuted.TLabel":
        kwargs.setdefault("text_color", COLORS["muted"])
        kwargs.setdefault("font", ("Segoe UI", 9))
    elif name == "Muted.TLabel":
        kwargs.setdefault("text_color", COLORS["muted"])
    elif name == "H1.TLabel":
        kwargs.setdefault("font", ("Segoe UI Semibold", 21, "bold"))
    elif name == "CardTitle.TLabel":
        kwargs.setdefault("font", ("Segoe UI Semibold", 13, "bold"))
    elif name == "CardValue.TLabel":
        kwargs.setdefault("font", ("Segoe UI", 20, "bold"))
    elif name == "Logo.TLabel":
        kwargs.setdefault("text_color", COLORS["accent"])
        kwargs.setdefault("font", ("Segoe UI Semibold", 25, "bold"))
    elif name == "Insight.TLabel":
        kwargs.setdefault("text_color", COLORS["amber"])
    elif name == "Status.TLabel":
        kwargs.setdefault("text_color", COLORS["muted"])
    elif name == "Accent.TButton":
        kwargs.setdefault("fg_color", COLORS["accent"])
        kwargs.setdefault("hover_color", "#55E7D8")
        kwargs.setdefault("text_color", COLORS["bg"])
        kwargs.setdefault("font", ("Segoe UI", 10, "bold"))
    elif name == "Danger.TButton":
        kwargs.setdefault("text_color", COLORS["red"])
    elif name == "Nav.TButton":
        kwargs.setdefault("fg_color", COLORS["surface"])
        kwargs.setdefault("text_color", COLORS["muted"])
        kwargs.setdefault("hover_color", COLORS["surface2"])
        kwargs.setdefault("anchor", "w")
    elif name == "NavActive.TButton":
        kwargs.setdefault("fg_color", COLORS["surface2"])
        kwargs.setdefault("text_color", COLORS["accent"])
        kwargs.setdefault("anchor", "w")
        kwargs.setdefault("font", ("Segoe UI", 11, "bold"))
    return kwargs


class Frame(ctk.CTkFrame):
    def __init__(self, master=None, **kwargs):
        super().__init__(master, **_style(kwargs))


class Label(ctk.CTkLabel):
    def __init__(self, master=None, **kwargs):
        text_var = kwargs.pop("textvariable", None)
        super().__init__(master, **_style(kwargs))
        if text_var is not None:
            self.configure(text=text_var.get())
            self._textvariable_trace = text_var.trace_add(
                "write", lambda *_: self.configure(text=text_var.get())
            )


class Button(ctk.CTkButton):
    def __init__(self, master=None, **kwargs):
        kwargs.setdefault("height", 32)
        kwargs.setdefault("corner_radius", 10)
        super().__init__(master, **_style(kwargs))

    def configure(self, *args, **kwargs):
        # The original navigation code switches ttk styles after creation.
        # Translate that operation to CustomTkinter colors and fonts.
        if "style" in kwargs:
            kwargs = _style(kwargs)
        return super().configure(*args, **kwargs)

    config = configure


class Entry(ctk.CTkEntry):
    def __init__(self, master=None, **kwargs):
        kwargs.pop("style", None)
        kwargs.pop("padding", None)
        kwargs.setdefault("fg_color", COLORS["surface2"])
        kwargs.setdefault("border_color", COLORS["border"])
        kwargs.setdefault("corner_radius", 10)
        super().__init__(master, **kwargs)


class ComboBox(ctk.CTkComboBox):
    def __init__(self, master=None, **kwargs):
        if "textvariable" in kwargs:
            kwargs["variable"] = kwargs.pop("textvariable")
        kwargs.pop("style", None)
        kwargs.pop("padding", None)
        kwargs.pop("state", None)
        kwargs.setdefault("fg_color", COLORS["surface2"])
        kwargs.setdefault("border_color", COLORS["border"])
        kwargs.setdefault("corner_radius", 10)
        super().__init__(master, **kwargs)


class Checkbutton(ctk.CTkCheckBox):
    def __init__(self, master=None, **kwargs):
        kwargs.pop("style", None)
        kwargs.pop("padding", None)
        super().__init__(master, **kwargs)


class Scale(ctk.CTkSlider):
    def __init__(self, master=None, **kwargs):
        kwargs.pop("style", None)
        kwargs.pop("padding", None)
        super().__init__(master, **kwargs)


ttk = SimpleNamespace(
    Frame=Frame, Label=Label, Button=Button, Entry=Entry, Combobox=ComboBox,
    Checkbutton=Checkbutton, Scale=Scale,
    Treeview=_ttk.Treeview, Scrollbar=_ttk.Scrollbar, Notebook=_ttk.Notebook,
)
