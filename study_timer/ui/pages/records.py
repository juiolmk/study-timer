# -*- coding: utf-8 -*-
"""记录页：搜索、按标签筛选、增删改（Canvas 自绘 + 分页懒加载）。

为什么不用“每行一套 Frame/Label”：
- 记录上千条时，Tk 的控件布局成本会线性膨胀；把行放在 Canvas 内嵌 Frame
  里更会被放大（实测 50 行普通布局 ~67ms，Canvas 内嵌 ~720ms）。
- 这里直接把卡片、文字、标签、操作区画在 Canvas 上，50 行只需几百个
  canvas item，首屏成本与记录总量脱钩。

交互：
- 单击“编辑/删除”文字命中对应操作；双击行主体也可编辑。
- 底部“加载更多”为可点击文字。
- 删除/编辑后保留已加载页数与滚动位置；搜索/标签/切页回到首屏。
"""

from __future__ import annotations

import logging
import tkinter as tk
import tkinter.font as tkfont
from tkinter import messagebox, ttk

from ..widgets import RoundedButton, make_entry, round_rect

logger = logging.getLogger(__name__)

#: 每次（首屏）最多渲染的记录条数
PAGE_SIZE = 50
#: 单行卡片高度
ROW_H = 66
#: 行间距
ROW_GAP = 10
#: 行内左右留白
PAD = 16
#: 卡片圆角
RADIUS = 10


class RecordsPage(tk.Frame):
    def __init__(self, master, app, theme):
        super().__init__(master, bg=theme.p.bg)
        self.app = app
        self.t = theme

        #: 当前筛选条件下的完整结果（未截断）
        self.rec_filtered = []
        #: 已渲染上限
        self._limit = PAGE_SIZE
        #: 当前可见行的命中区域与记录
        self._rows = []
        #: “加载更多”文字区域；None 表示不可点击 / 无页脚
        self._footer_box = None
        self._footer_text = ""
        #: 画布宽度与内容高度（滚动恢复用）
        self._canvas_w = 0
        self._content_height = 1

        self._font_title = tkfont.Font(font=theme.font_bold)
        self._font_small = tkfont.Font(font=theme.font_sm)

        self._build()
        self.refresh(reset_limit=True)

    # ------------------------------------------------------------ 构建
    def _build(self):
        p = self.t.p

        header = tk.Frame(self, bg=p.bg)
        header.pack(fill="x", padx=28, pady=(22, 10))
        tk.Label(header, text="学习记录", font=self.t.font_h1,
                 bg=p.bg, fg=p.text).pack(side="left")
        self.count_label = tk.Label(header, text="", font=self.t.font_sm,
                                    bg=p.bg, fg=p.muted)
        self.count_label.pack(side="left", padx=12, pady=(10, 0))

        toolbar = tk.Frame(self, bg=p.bg)
        toolbar.pack(fill="x", padx=28, pady=(0, 10))

        self.search_var = tk.StringVar()
        search = make_entry(toolbar, self.t, textvariable=self.search_var)
        search.pack(side="left", fill="x", expand=True)
        search.bind("<KeyRelease>", lambda _e: self.refresh(reset_limit=True))

        self.tag_var = tk.StringVar(value="全部标签")
        self.tag_combo = ttk.Combobox(
            toolbar, textvariable=self.tag_var, state="readonly",
            font=self.t.font, width=12,
        )
        self.tag_combo.pack(side="left", padx=8)
        self.tag_combo.bind("<<ComboboxSelected>>",
                            lambda _e: self.refresh(reset_limit=True))

        RoundedButton(toolbar, self.t, "＋ 补记",
                      command=self.app.open_quick_record_dialog,
                      variant="success", height=38).pack(side="left")

        # Canvas 直接绘制行，避免“Canvas 内嵌 Frame”的布局放大
        self.list_frame = tk.Frame(self, bg=p.bg)
        self.list_frame.pack(fill="both", expand=True, padx=28, pady=(0, 18))

        self.canvas = tk.Canvas(self.list_frame, bg=p.bg,
                                highlightthickness=0, bd=0)
        self.scrollbar = ttk.Scrollbar(
            self.list_frame, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        self.canvas.bind("<Configure>", self._on_configure)
        self.canvas.bind("<Button-1>", self._on_click)
        self.canvas.bind("<Double-Button-1>", self._on_double_click)
        self.canvas.bind("<Motion>", self._on_motion)
        self.canvas.bind("<MouseWheel>", self._on_wheel)

    # ------------------------------------------------------------ 刷新
    def refresh(self, reset_limit=False):
        """重新计算筛选结果并重绘。

        Args:
            reset_limit: ``True`` 表示回到首屏（搜索、标签筛选、切换页面）；
                ``False``（默认）保留当前已加载条数与滚动位置（删除/编辑）。
        """
        self._update_tag_values()

        keyword = self.search_var.get().strip().lower()
        tag = self.tag_var.get()

        records = sorted(self.app.store.records,
                         key=lambda r: (r.date, r.start), reverse=True)
        if keyword:
            records = [
                r for r in records
                if keyword in f"{r.title} {r.note} {r.tag} {r.date}".lower()
            ]
        if tag and tag != "全部标签":
            records = [r for r in records if (r.tag.strip() or "未分类") == tag]

        self.rec_filtered = records
        total = len(records)

        if reset_limit or total == 0:
            self._limit = PAGE_SIZE
        else:
            # 至少一页、至多全部：数据变少时不留下空页
            self._limit = min(max(self._limit, PAGE_SIZE), total)

        self.count_label.configure(text=f"共 {total} 条")

        top = 0.0 if reset_limit else self._scroll_top()
        self._redraw()
        self._restore_scroll(top)

    # ------------------------------------------------------------ 绘制
    def _redraw(self):
        """按当前 ``_limit`` 重绘所有可见行与页脚。"""
        canvas = self.canvas
        canvas.delete("all")
        self._rows = []
        self._footer_box = None
        self._footer_text = ""

        width = self._canvas_w or canvas.winfo_width()
        if width <= 10:
            width = 900  # 尚未完成布局：先按默认宽度画，<Configure> 会再校正

        p = self.t.p
        total = len(self.rec_filtered)

        if total == 0:
            canvas.create_text(width / 2, 60, text="没有匹配的记录",
                               font=self.t.font, fill=p.muted)
            self._content_height = 140
            canvas.configure(scrollregion=(0, 0, width, self._content_height))
            return

        visible = self.rec_filtered[:self._limit]
        y = 0
        for record in visible:
            self._draw_row(record, y, width)
            y += ROW_H + ROW_GAP

        footer_y = y + 8
        if len(visible) < total:
            text = f"加载更多（已显示 {len(visible)} / 共 {total} 条）"
            item = canvas.create_text(width / 2, footer_y + 10, text=text,
                                      font=self.t.font_sm, fill=p.primary)
            bbox = canvas.bbox(item)
            if bbox:
                self._footer_box = bbox
                self._footer_text = text
        else:
            text = f"已显示全部 {total} 条"
            canvas.create_text(width / 2, footer_y + 10, text=text,
                               font=self.t.font_sm, fill=p.muted)
            self._footer_text = text

        self._content_height = max(footer_y + 40, 1)
        canvas.configure(scrollregion=(0, 0, width, self._content_height))

    def _draw_row(self, record, y0, width):
        """画一行卡片：标题、标签、副标题、时长、编辑/删除。"""
        p = self.t.p
        canvas = self.canvas

        round_rect(canvas, 0, y0, width - 2, y0 + ROW_H, RADIUS,
                   fill=p.surface, outline=p.border)

        # 标签（先量宽度，给标题留空间）
        tag_text = record.tag.strip() or "未分类"
        tag_max = min(max(60, int(width * 0.28)), 160)
        tag_text = self._fit(tag_text, self._font_small, tag_max - 16)
        tag_w = self._font_small.measure(tag_text) + 16

        right_reserve = 110
        max_title_w = max(80, width - PAD * 2 - tag_w - 12 - right_reserve)
        title = self._fit(record.title or "(未命名)",
                          self._font_title, max_title_w)
        canvas.create_text(PAD, y0 + 20, text=title, anchor="w",
                           font=self.t.font_bold, fill=p.text)
        title_w = self._font_title.measure(title)

        tag_x = PAD + title_w + 10
        round_rect(canvas, tag_x, y0 + 11, tag_x + tag_w, y0 + 29,
                   8, fill=p.surface_alt, outline="")
        canvas.create_text(tag_x + tag_w / 2, y0 + 20, text=tag_text,
                           font=self.t.font_sm, fill=p.primary)

        subtitle = f"{record.date}  {self._hhmm(record.start)} - {self._hhmm(record.end)}"
        if record.note:
            subtitle += f"  ·  {record.note}"
        subtitle = self._fit(subtitle, self._font_small,
                             max(80, width - PAD * 2 - 92))
        canvas.create_text(PAD, y0 + 44, text=subtitle, anchor="w",
                           font=self.t.font_sm, fill=p.muted)

        # 时长
        canvas.create_text(width - PAD, y0 + 20,
                           text=self.app.fmt(record.duration_min), anchor="e",
                           font=self.t.font_bold, fill=p.primary)

        # 删除
        delete_w = self._font_small.measure("删除")
        delete_box = (width - PAD - delete_w - 6, y0 + 34,
                      width - PAD + 6, y0 + 56)
        canvas.create_text(width - PAD, y0 + 45, text="删除", anchor="e",
                           font=self.t.font_sm, fill=p.danger)

        # 编辑
        edit_right = width - PAD - delete_w - 24
        edit_w = self._font_small.measure("编辑")
        edit_box = (edit_right - edit_w - 6, y0 + 34,
                    edit_right + 6, y0 + 56)
        canvas.create_text(edit_right, y0 + 45, text="编辑", anchor="e",
                           font=self.t.font_sm, fill=p.muted)

        self._rows.append({
            "record": record,
            "y0": y0,
            "y1": y0 + ROW_H,
            "edit": edit_box,
            "delete": delete_box,
        })

    # ------------------------------------------------------------ 交互
    def _on_configure(self, event):
        if event.width <= 1:
            return
        if abs(event.width - self._canvas_w) > 1:
            self._canvas_w = event.width
            self._redraw()

    def _on_click(self, event):
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)

        if self._footer_box and self._in(self._footer_box, x, y):
            self._load_more()
            return

        for row in self._rows:
            if row["y0"] <= y <= row["y1"]:
                if self._in(row["edit"], x, y):
                    self.app.open_record_dialog(record=row["record"])
                elif self._in(row["delete"], x, y):
                    self._delete(row["record"])
                return

    def _on_double_click(self, event):
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        for row in self._rows:
            if row["y0"] <= y <= row["y1"]:
                if not (self._in(row["edit"], x, y)
                        or self._in(row["delete"], x, y)):
                    self.app.open_record_dialog(record=row["record"])
                return

    def _on_motion(self, event):
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        over = bool(self._footer_box and self._in(self._footer_box, x, y))
        if not over:
            for row in self._rows:
                if row["y0"] <= y <= row["y1"] and (
                        self._in(row["edit"], x, y)
                        or self._in(row["delete"], x, y)):
                    over = True
                    break
        self.canvas.configure(cursor="hand2" if over else "")

    def _on_wheel(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    @staticmethod
    def _in(box, x, y):
        return box[0] <= x <= box[2] and box[1] <= y <= box[3]

    def _load_more(self):
        """加载下一页并保持当前滚动位置。"""
        total = len(self.rec_filtered)
        if self._limit >= total:
            return
        top = self._scroll_top()
        self._limit = min(total, self._limit + PAGE_SIZE)
        self._redraw()
        self._restore_scroll(top)

    # ------------------------------------------------------------ 滚动
    def _scroll_top(self):
        try:
            return max(0.0, float(self.canvas.canvasy(0)))
        except Exception:
            logger.debug("读取记录列表滚动位置失败", exc_info=True)
            return 0.0

    def _restore_scroll(self, top):
        try:
            self.canvas.update_idletasks()
            fraction = max(0.0, top) / max(1, self._content_height)
            self.canvas.yview_moveto(fraction)
            # scrollregion 可能异步更新，idle 后再校正一次
            self.after_idle(lambda: self.canvas.yview_moveto(fraction))
        except Exception:
            logger.debug("恢复滚动位置失败", exc_info=True)

    # ------------------------------------------------------------ 工具
    def _update_tag_values(self):
        tags = ["全部标签"] + self.app.store.tags()
        self.tag_combo.configure(values=tags)
        if self.tag_var.get() not in tags:
            self.tag_var.set("全部标签")

    @staticmethod
    def _fit(text, font, max_width):
        """按像素宽度截断文本，超出部分用省略号。"""
        if not text or max_width <= 0:
            return ""
        if font.measure(text) <= max_width:
            return text
        low, high = 0, len(text)
        while low < high:
            mid = (low + high + 1) // 2
            if font.measure(text[:mid] + "…") <= max_width:
                low = mid
            else:
                high = mid - 1
        return text[:low] + "…" if low < len(text) else text

    @staticmethod
    def _hhmm(text):
        if not text:
            return "-"
        return text[-5:] if len(text) >= 5 else text

    # ------------------------------------------------------------ 删除
    def _delete(self, record):
        label = record.title or record.date
        if not messagebox.askyesno("确认删除", f"确定删除「{label}」这条记录吗？"):
            return

        self.app.store.records.remove(record)
        day = record.date
        if self.app.stats.minutes_on(day) == 0:
            self.app.store.checkins.discard(day)

        self.app.repo.save(self.app.store)
        self.app.refresh_all()
