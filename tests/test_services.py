# -*- coding: utf-8 -*-
"""服务层单元测试。"""

import unittest
from datetime import date

from study_timer.models import Record, Store
from study_timer.services import StatsService, TimerService, choose_break


class FakeClock:
    """可手动推进的单调时钟。"""

    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


class StatsServiceTest(unittest.TestCase):
    def setUp(self):
        self.today = date(2026, 10, 20)
        records = [
            Record("1", "2026-10-20", "", "", 30, "数学题", "", "数学"),
            Record("2", "2026-10-20", "", "", 45, "阅读理解", "", "英语"),
            Record("3", "2026-10-19", "", "", 60, "函数", "", "数学"),
            Record("4", "2026-10-18", "", "", 20, "力学", "", "物理"),
        ]
        checkins = {"2026-10-20", "2026-10-19", "2026-10-18", "2026-10-16"}
        self.store = Store(records=records, checkins=checkins)
        self.stats = StatsService(self.store)

    def test_minutes_on(self):
        self.assertEqual(self.stats.minutes_on("2026-10-20"), 75)
        self.assertEqual(self.stats.minutes_on("2026-10-17"), 0)

    def test_current_streak(self):
        self.assertEqual(self.stats.current_streak(self.today), 3)

    def test_current_streak_without_today(self):
        # 今天未打卡时从昨天开始算，保留一天宽限
        self.assertEqual(self.stats.current_streak(date(2026, 10, 21)), 3)

    def test_longest_streak(self):
        self.assertEqual(self.stats.longest_streak(), 3)

    def test_series(self):
        series = self.stats.series(7, self.today)
        self.assertEqual(len(series), 7)
        self.assertEqual(series[0][0], "2026-10-14")
        self.assertEqual(series[-1], ("2026-10-20", 75))

    def test_heatmap_cells_shape(self):
        columns = self.stats.heatmap_cells(2, self.today)
        self.assertEqual(len(columns), 2)
        for column in columns:
            self.assertEqual(len(column), 7)
        matched = [cell[0] for column in columns for cell in column if cell[0] == self.today]
        self.assertEqual(len(matched), 1)

    def test_tag_totals(self):
        days = {day for day, _ in self.stats.series(7, self.today)}
        totals = self.stats.tag_totals(days)
        self.assertEqual(totals["数学"], 90)
        self.assertEqual(totals["英语"], 45)
        self.assertEqual(totals["物理"], 20)


class TimerServiceTest(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.timer = TimerService(self.clock)

    def test_stopwatch_flow(self):
        self.timer.configure("stopwatch")
        self.timer.start()
        self.clock.now = 10
        self.assertAlmostEqual(self.timer.elapsed(), 10)

        self.timer.pause()
        self.clock.now = 30
        self.assertAlmostEqual(self.timer.elapsed(), 10)

        self.timer.resume()
        self.clock.now = 35
        self.assertAlmostEqual(self.timer.elapsed(), 15)

        self.assertAlmostEqual(self.timer.stop(), 15)
        self.assertTrue(self.timer.is_idle)

    def test_countdown_remaining(self):
        self.timer.configure("countdown", 1)
        self.timer.start()
        self.clock.now = 30
        self.assertAlmostEqual(self.timer.remaining(), 30)
        self.clock.now = 60
        self.assertAlmostEqual(self.timer.remaining(), 0)

    def test_stopwatch_has_no_remaining(self):
        self.timer.configure("stopwatch")
        self.assertIsNone(self.timer.remaining())


class BreakChoiceTest(unittest.TestCase):
    def test_short_break_before_long(self):
        for completed in (1, 2, 3):
            phase, minutes = choose_break(completed, 4, 5, 15)
            self.assertEqual((phase, minutes), ("short_break", 5))

    def test_long_break_every_fourth(self):
        for completed in (4, 8):
            phase, minutes = choose_break(completed, 4, 5, 15)
            self.assertEqual((phase, minutes), ("long_break", 15))

    def test_custom_rounds(self):
        phase, minutes = choose_break(3, 3, 10, 30)
        self.assertEqual((phase, minutes), ("long_break", 30))

    def test_zero_rounds_is_short(self):
        phase, minutes = choose_break(0, 4, 5, 15)
        self.assertEqual((phase, minutes), ("short_break", 5))


if __name__ == "__main__":
    unittest.main()
