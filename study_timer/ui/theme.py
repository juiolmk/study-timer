# -*- coding: utf-8 -*-
"""主题：浅色/深色配色、字体与 ttk 样式。"""

from __future__ import annotations

from dataclasses import dataclass
from tkinter import ttk

FONT_FAMILY = "Microsoft YaHei UI"


def font(size, weight="normal"):
    return (FONT_FAMILY, size, weight)


def mix(c1: str, c2: str, t: float) -> str:
    """在两个 #rrggbb 颜色之间线性插值。"""
    t = max(0.0, min(1.0, t))
    a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{int(a[i] + (b[i] - a[i]) * t):02x}" for i in range(3))


@dataclass(frozen=True)
class Palette:
    name: str
    bg: str
    surface: str
    surface_alt: str
    text: str
    muted: str
    border: str
    primary: str
    primary_hover: str
    primary_press: str
    on_primary: str
    success: str
    warning: str
    danger: str
    track: str


LIGHT = Palette(
    name="light",
    bg="#f3f6fb",
    surface="#ffffff",
    surface_alt="#eef2f9",
    text="#1a2330",
    muted="#6b7789",
    border="#e4e9f2",
    primary="#4f6df5",
    primary_hover="#3f5ce4",
    primary_press="#3550cf",
    on_primary="#ffffff",
    success="#1fa971",
    warning="#e6a23c",
    danger="#e5484d",
    track="#e2e8f3",
)

DARK = Palette(
    name="dark",
    bg="#141922",
    surface="#1d2531",
    surface_alt="#252f3d",
    text="#e8eef7",
    muted="#94a2b6",
    border="#2b3646",
    primary="#6c86ff",
    primary_hover="#5c78f5",
    primary_press="#4f6ae6",
    on_primary="#ffffff",
    success="#35b982",
    warning="#e6a23c",
    danger="#f2555a",
    track="#2a3544",
)


def get_palette(name: str) -> Palette:
    return DARK if name == "dark" else LIGHT


class Theme:
    """把配色与字体打包，供各页面使用。"""

    def __init__(self, name: str = "light"):
        self.p = get_palette(name)
        self.name = self.p.name

        self.font_sm = font(9)
        self.font = font(10)
        self.font_bold = font(10, "bold")
        self.font_h2 = font(13, "bold")
        self.font_h1 = font(19, "bold")
        self.font_num = font(22, "bold")
        self.font_timer = font(50, "bold")

    def mix(self, c1: str, c2: str, t: float) -> str:
        return mix(c1, c2, t)


def configure_ttk(root, palette: Palette) -> None:
    """统一 ttk 控件（下拉框/滚动条）的外观。"""
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except Exception:
        pass

    style.configure(
        "TCombobox",
        fieldbackground=palette.surface_alt,
        background=palette.surface_alt,
        foreground=palette.text,
        bordercolor=palette.border,
        lightcolor=palette.border,
        darkcolor=palette.border,
        arrowcolor=palette.muted,
        padding=6,
    )
    style.map(
        "TCombobox",
        fieldbackground=[("readonly", palette.surface_alt)],
        foreground=[("readonly", palette.text)],
        selectbackground=[("readonly", palette.surface_alt)],
        selectforeground=[("readonly", palette.text)],
    )
    style.configure(
        "Vertical.TScrollbar",
        background=palette.surface_alt,
        troughcolor=palette.bg,
        bordercolor=palette.bg,
        arrowcolor=palette.muted,
    )
    style.map("Vertical.TScrollbar", background=[("active", palette.border)])

    # Combobox 下拉列表（Listbox）配色
    root.option_add("*TCombobox*Listbox.background", palette.surface)
    root.option_add("*TCombobox*Listbox.foreground", palette.text)
    root.option_add("*TCombobox*Listbox.selectBackground", palette.primary)
    root.option_add("*TCombobox*Listbox.selectForeground", palette.on_primary)
