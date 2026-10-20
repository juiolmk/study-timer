# -*- coding: utf-8 -*-
"""可复用的界面组件。"""

from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

from .theme import mix


# ---------------------------------------------------------------- 基础绘制
def round_rect(canvas: tk.Canvas, x1, y1, x2, y2, radius, **kwargs):
    """在 Canvas 上绘制圆角矩形。"""
    radius = min(radius, (x2 - x1) / 2, (y2 - y1) / 2)
    points = [
        x1 + radius, y1, x2 - radius, y1, x2, y1, x2, y1 + radius,
        x2, y2 - radius, x2, y2, x2 - radius, y2, x1 + radius, y2,
        x1, y2, x1, y2 - radius, x1, y1 + radius, x1, y1,
    ]
    return canvas.create_polygon(points, smooth=True, **kwargs)


def make_entry(master, theme, width=None, textvariable=None) -> tk.Entry:
    p = theme.p
    entry = tk.Entry(
        master,
        font=theme.font,
        bg=p.surface_alt,
        fg=p.text,
        insertbackground=p.text,
        relief="flat",
        bd=0,
        highlightthickness=1,
        highlightbackground=p.border,
        highlightcolor=p.primary,
    )
    if width:
        entry.configure(width=width)
    if textvariable is not None:
        entry.configure(textvariable=textvariable)
    return entry


# ---------------------------------------------------------------- 卡片
class Card(tk.Frame):
    def __init__(self, master, theme, **kwargs):
        super().__init__(
            master,
            bg=theme.p.surface,
            highlightbackground=theme.p.border,
            highlightthickness=1,
            bd=0,
            **kwargs,
        )


# ---------------------------------------------------------------- 圆角按钮
class RoundedButton(tk.Canvas):
    def __init__(self, master, theme, text, command=None, width=None, height=42,
                 radius=12, variant="primary", font=None, padx=22):
        super().__init__(master, height=height, highlightthickness=0, bd=0, bg=master.cget("bg"))
        self._theme = theme
        self._command = command
        self._radius = radius
        self._text = text
        self._font = font or theme.font_bold
        self._pad = padx
        self._variant = variant
        self._enabled = True
        self._state = "normal"

        self._apply_variant()
        self._measure(width)
        self._draw()

        self.configure(cursor="hand2")
        self.bind("<Configure>", lambda _e: self._draw())
        self.bind("<Enter>", lambda _e: self._set_state("hover"))
        self.bind("<Leave>", lambda _e: self._set_state("normal"))
        self.bind("<ButtonPress-1>", lambda _e: self._set_state("press"))
        self.bind("<ButtonRelease-1>", self._on_release)

    def _apply_variant(self):
        p = self._theme.p
        if self._variant == "success":
            self._bg = p.success
            self._hover = mix(p.success, "#000000", 0.10)
            self._press = mix(p.success, "#000000", 0.18)
            self._fg = "#ffffff"
        elif self._variant == "danger":
            self._bg = p.danger
            self._hover = mix(p.danger, "#000000", 0.10)
            self._press = mix(p.danger, "#000000", 0.18)
            self._fg = "#ffffff"
        elif self._variant == "ghost":
            self._bg = p.surface_alt
            self._hover = p.border
            self._press = p.track
            self._fg = p.text
        else:  # primary
            self._bg = p.primary
            self._hover = p.primary_hover
            self._press = p.primary_press
            self._fg = p.on_primary

    def _measure(self, width):
        f = tkfont.Font(font=self._font)
        w = width or (f.measure(self._text) + self._pad * 2)
        self.configure(width=max(52, w))

    def _set_state(self, state):
        if not self._enabled:
            return
        self._state = state
        self._draw()

    def _on_release(self, event):
        if not self._enabled:
            return
        self._state = "hover"
        self._draw()
        if 0 <= event.x <= self.winfo_width() and 0 <= event.y <= self.winfo_height():
            if self._command:
                self._command()

    def _draw(self):
        self.delete("all")
        try:
            width = self.winfo_width() or int(self.cget("width"))
            height = self.winfo_height() or int(self.cget("height"))
        except Exception:
            width, height = 120, 42
        if width <= 1:
            width = 120
        if height <= 1:
            height = 42

        if self._enabled:
            fill = {"normal": self._bg, "hover": self._hover, "press": self._press}.get(self._state, self._bg)
            fg = self._fg
        else:
            fill = self._theme.p.track
            fg = self._theme.p.muted

        round_rect(self, 1, 1, width - 1, height - 1, self._radius, fill=fill, outline="")
        self.create_text(width / 2, height / 2, text=self._text, fill=fg, font=self._font)

    def set_enabled(self, enabled: bool):
        enabled = bool(enabled)
        if enabled == self._enabled:
            return
        self._enabled = enabled
        self.configure(cursor="hand2" if enabled else "arrow")
        self._draw()

    def set_text(self, text: str):
        if text == self._text:
            return
        self._text = text
        self._measure(None)
        self._draw()


# ---------------------------------------------------------------- 分段控件
class Segmented(tk.Frame):
    def __init__(self, master, theme, options, command=None, index=0):
        super().__init__(master, bg=theme.p.surface_alt)
        self._theme = theme
        self._command = command
        self.index = index
        self._labels = []

        for i, option in enumerate(options):
            label = tk.Label(
                self, text=option, font=theme.font_bold,
                padx=14, pady=7, cursor="hand2",
            )
            label.pack(side="left", padx=2, pady=2)
            label.bind("<Button-1>", lambda _e, i=i: self.select(i))
            self._labels.append(label)

        self._style()

    def _style(self):
        p = self._theme.p
        for i, label in enumerate(self._labels):
            if i == self.index:
                label.configure(bg=p.primary, fg=p.on_primary)
            else:
                label.configure(bg=p.surface_alt, fg=p.muted)

    def select(self, index, notify=True):
        if index == self.index:
            self._style()
            return
        self.index = index
        self._style()
        if notify and self._command:
            self._command(index)


# ---------------------------------------------------------------- 进度环
class RingProgress(tk.Canvas):
    def __init__(self, master, theme, size=156, thickness=13):
        super().__init__(master, width=size, height=size, bg=master.cget("bg"), highlightthickness=0)
        self._theme = theme
        self._size = size
        self._thickness = thickness
        self._ratio = 0.0
        self._big = "0%"
        self._small = ""
        self._color = theme.p.primary
        self._draw()

    def set(self, ratio, big, small="", color=None):
        self._ratio = max(0.0, min(1.0, ratio))
        self._big = big
        self._small = small
        self._color = color or self._theme.p.primary
        self._draw()

    def _draw(self):
        self.delete("all")
        size = self._size
        thick = self._thickness
        pad = thick / 2 + 2
        x1, y1, x2, y2 = pad, pad, size - pad, size - pad

        self.create_oval(x1, y1, x2, y2, outline=self._theme.p.track, width=thick)
        if self._ratio > 0:
            self.create_arc(
                x1, y1, x2, y2, start=90, extent=-360 * self._ratio,
                style=tk.ARC, outline=self._color, width=thick,
            )
        self.create_text(size / 2, size / 2 - 8, text=self._big,
                         fill=self._theme.p.text, font=self._theme.font_num)
        if self._small:
            self.create_text(size / 2, size / 2 + 18, text=self._small,
                             fill=self._theme.p.muted, font=self._theme.font_sm)


# ---------------------------------------------------------------- 热力图
class Heatmap(tk.Canvas):
    def __init__(self, master, theme, weeks=12, cell=14, gap=4, on_hover=None):
        self._theme = theme
        self._weeks = weeks
        self._cell = cell
        self._gap = gap
        self._on_hover = on_hover
        self._rects = []

        width = 30 + weeks * (cell + gap)
        height = 10 + 7 * (cell + gap)
        super().__init__(master, width=width, height=height,
                         bg=master.cget("bg"), highlightthickness=0)

        self.bind("<Motion>", self._motion)
        self.bind("<Leave>", self._leave)

    def render(self, cells, goal):
        self.delete("all")
        self._rects = []
        p = self._theme.p
        cell, gap = self._cell, self._gap
        ox, oy = 30, 10
        goal = max(1, goal)

        for row, text in {0: "一", 2: "三", 4: "五", 6: "日"}.items():
            self.create_text(
                ox - 8, oy + row * (cell + gap) + cell / 2,
                text=text, anchor="e", fill=p.muted, font=self._theme.font_sm,
            )

        for column_index, column in enumerate(cells):
            for row_index, (day, minutes, future) in enumerate(column):
                x = ox + column_index * (cell + gap)
                y = oy + row_index * (cell + gap)

                if future or minutes is None or minutes <= 0:
                    color = p.track
                else:
                    color = mix(p.track, p.primary, max(0.18, min(1.0, minutes / goal)))

                round_rect(self, x, y, x + cell, y + cell, 3, fill=color, outline="")
                self._rects.append((x, y, x + cell, y + cell, day.isoformat(), minutes, future))

    def _motion(self, event):
        for x1, y1, x2, y2, day, minutes, future in self._rects:
            if x1 <= event.x <= x2 and y1 <= event.y <= y2:
                if self._on_hover:
                    self._on_hover(day, None if future else minutes)
                return

    def _leave(self, _event):
        if self._on_hover:
            self._on_hover(None, None)


# ---------------------------------------------------------------- 滚动容器
class ScrollableFrame(tk.Frame):
    def __init__(self, master, theme):
        super().__init__(master, bg=theme.p.bg)
        self._theme = theme

        self.canvas = tk.Canvas(self, bg=theme.p.bg, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        self.inner = tk.Frame(self.canvas, bg=theme.p.bg)
        self._window = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")

        self.inner.bind("<Configure>", self._on_inner_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.canvas.bind("<Enter>", lambda _e: self.canvas.bind_all("<MouseWheel>", self._on_wheel))
        self.canvas.bind("<Leave>", lambda _e: self.canvas.unbind_all("<MouseWheel>"))

    def _on_inner_configure(self, _event):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self.canvas.itemconfigure(self._window, width=event.width)

    def _on_wheel(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")


# ---------------------------------------------------------------- 侧边栏按钮
class SidebarButton(tk.Frame):
    def __init__(self, master, theme, text, command):
        super().__init__(master, bg=theme.p.surface, cursor="hand2")
        self._theme = theme
        self._command = command
        self._active = False

        self._bar = tk.Frame(self, bg=theme.p.surface, width=3)
        self._bar.pack(side="left", fill="y")

        self._label = tk.Label(
            self, text=text, font=theme.font_bold, bg=theme.p.surface,
            fg=theme.p.muted, anchor="w", padx=14, pady=9,
        )
        self._label.pack(side="left", fill="x", expand=True)

        for widget in (self, self._label):
            widget.bind("<Button-1>", lambda _e: self._command())
            widget.bind("<Enter>", self._hover)
            widget.bind("<Leave>", self._leave)

    def _paint(self, color):
        self.configure(bg=color)
        self._label.configure(bg=color)
        self._bar.configure(bg=color if not self._active else self._theme.p.primary)

    def _hover(self, _event):
        if not self._active:
            self._paint(self._theme.p.surface_alt)

    def _leave(self, _event):
        if not self._active:
            self._paint(self._theme.p.surface)

    def set_active(self, active: bool):
        self._active = active
        p = self._theme.p
        if active:
            self._paint(p.surface_alt)
            self._bar.configure(bg=p.primary)
            self._label.configure(fg=p.primary)
        else:
            self._paint(p.surface)
            self._bar.configure(bg=p.surface)
            self._label.configure(fg=p.muted)
