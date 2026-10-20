# -*- coding: utf-8 -*-
"""领域服务：计时器与统计。

两者都不依赖 GUI，便于单元测试。
"""

from __future__ import annotations

import time
from datetime import date, datetime, timedelta

from .models import Store

MODE_STOPWATCH = "stopwatch"
MODE_COUNTDOWN = "countdown"

PHASE_WORK = "work"
PHASE_SHORT_BREAK = "short_break"
PHASE_LONG_BREAK = "long_break"


def choose_break(completed_rounds: int, rounds_per_long: int,
                 short_min: int, long_min: int):
    """根据已完成轮数选择休息类型与分钟数。

    第 1..n-1 轮为短休，第 n 轮（n = rounds_per_long）为长休，循环往复。
    """
    rounds_per_long = max(1, int(rounds_per_long))
    if completed_rounds > 0 and completed_rounds % rounds_per_long == 0:
        return PHASE_LONG_BREAK, int(long_min)
    return PHASE_SHORT_BREAK, int(short_min)


class TimerService:
    """秒表 / 倒计时。

    使用可注入的单调时钟，避免系统时间被修改时计时跳变。
    """

    def __init__(self, clock=time.monotonic):
        self._clock = clock
        self.mode = MODE_STOPWATCH
        self.target = 0.0          # 倒计时总秒数
        self._running = False
        self._paused = False
        self._acc = 0.0            # 已累计秒数
        self._start = 0.0

    # ---------- 状态 ----------
    @property
    def is_running(self) -> bool:
        return self._running and not self._paused

    @property
    def is_paused(self) -> bool:
        return self._running and self._paused

    @property
    def is_active(self) -> bool:
        return self._running

    @property
    def is_idle(self) -> bool:
        return not self._running

    # ---------- 配置 ----------
    def configure(self, mode: str = MODE_STOPWATCH, target_minutes: float = 0) -> None:
        if self._running:
            return
        self.mode = MODE_COUNTDOWN if mode == MODE_COUNTDOWN else MODE_STOPWATCH
        self.target = float(target_minutes) * 60 if self.mode == MODE_COUNTDOWN else 0.0
        self._acc = 0.0

    # ---------- 控制 ----------
    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._paused = False
        self._acc = 0.0
        self._start = self._clock()

    def pause(self) -> None:
        if not self.is_running:
            return
        self._acc += self._clock() - self._start
        self._paused = True

    def resume(self) -> None:
        if not self.is_paused:
            return
        self._paused = False
        self._start = self._clock()

    def stop(self) -> float:
        """结束并返回本次计时秒数，随后回到空闲。"""
        seconds = self.elapsed()
        self._running = False
        self._paused = False
        self._acc = 0.0
        self._start = 0.0
        return seconds

    def reset(self) -> None:
        self._running = False
        self._paused = False
        self._acc = 0.0
        self._start = 0.0

    # ---------- 读数 ----------
    def elapsed(self) -> float:
        if self._running and not self._paused:
            return self._acc + (self._clock() - self._start)
        return self._acc

    def remaining(self):
        """倒计时剩余秒数；秒表模式返回 None。"""
        if self.mode != MODE_COUNTDOWN:
            return None
        return max(0.0, self.target - self.elapsed())


class StatsService:
    """基于 Store 的统计计算。"""

    def __init__(self, store: Store):
        self.store = store

    # ---------- 基础 ----------
    def minutes_on(self, day: str) -> int:
        return sum(r.duration_min for r in self.store.records if r.date == day)

    def current_streak(self, today: date | None = None) -> int:
        """当前连续打卡天数。

        今天未打卡时，从昨天开始计算（保留一天宽限）。
        """
        today = today or date.today()
        checkins = set(self.store.checkins)
        if not checkins:
            return 0

        cursor = today
        if cursor.isoformat() not in checkins:
            cursor = cursor - timedelta(days=1)

        streak = 0
        while cursor.isoformat() in checkins:
            streak += 1
            cursor -= timedelta(days=1)
        return streak

    def longest_streak(self) -> int:
        dates = sorted(self.store.checkins)
        if not dates:
            return 0
        best = current = 1
        for prev, cur in zip(dates, dates[1:]):
            try:
                delta = (datetime.strptime(cur, "%Y-%m-%d") -
                         datetime.strptime(prev, "%Y-%m-%d")).days
            except Exception:
                current = 1
                continue
            if delta == 1:
                current += 1
                best = max(best, current)
            else:
                current = 1
        return best

    def series(self, days: int, today: date | None = None):
        """返回最近 days 天：[(YYYY-MM-DD, 分钟), ...]，按时间升序。"""
        today = today or date.today()
        result = []
        for offset in range(days - 1, -1, -1):
            day = (today - timedelta(days=offset)).isoformat()
            result.append((day, self.minutes_on(day)))
        return result

    # ---------- 热力图 ----------
    def heatmap_cells(self, weeks: int = 12, today: date | None = None):
        """按“周”组织热力图单元格。

        返回 [[ (date, minutes|None, is_future), ...7 ], ...weeks]。
        每列一周（周一→周日），最后一列为本周。
        """
        today = today or date.today()
        monday = today - timedelta(days=today.weekday())
        start = monday - timedelta(weeks=weeks - 1)

        columns = []
        for week_index in range(weeks):
            column = []
            for weekday in range(7):
                day = start + timedelta(days=week_index * 7 + weekday)
                if day > today:
                    column.append((day, None, True))
                else:
                    column.append((day, self.minutes_on(day.isoformat()), False))
            columns.append(column)
        return columns

    # ---------- 标签 ----------
    def tag_totals(self, days=None):
        """按标签汇总分钟数；days 为日期字符串集合，None 表示全部。"""
        totals = {}
        for record in self.store.records:
            if days is not None and record.date not in days:
                continue
            key = record.tag.strip() if record.tag and record.tag.strip() else "未分类"
            totals[key] = totals.get(key, 0) + record.duration_min
        return totals

    def total_checkin_days(self) -> int:
        return len(self.store.checkins)
