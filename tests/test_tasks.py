# -*- coding: utf-8 -*-
"""任务模型、排序、顺延与时长汇总测试。"""

import unittest

from study_timer.models import Record, Store, Task
from study_timer.tasks import (
    PRIORITY_LABELS,
    carry_over_unfinished,
    sort_tasks,
    task_minutes,
    today_tasks,
)

DAY = "2026-10-21"


def _task(task_id, title, priority=1, done=False, day=DAY, created_at=""):
    return Task(
        id=task_id, date=day, title=title, priority=priority,
        tag="", done=done, created_at=created_at or task_id,
    )


class TaskModelTest(unittest.TestCase):
    def test_priority_labels(self):
        self.assertEqual(PRIORITY_LABELS, ("高", "中", "低"))

    def test_roundtrip_and_priority_clamp(self):
        task = Task.from_dict({
            "id": "t1", "date": DAY, "title": "写论文",
            "priority": 9, "tag": "论文", "done": True,
        })
        self.assertEqual(task.priority, 2)
        self.assertEqual(Task.from_dict(task.to_dict()), task)

    def test_invalid_task_rejected(self):
        with self.assertRaises(Exception):
            Task.from_dict({"id": "t1", "date": DAY, "title": ""})

    def test_record_task_id_roundtrip_and_legacy(self):
        record = Record(
            "r1", DAY, f"{DAY} 09:00", f"{DAY} 09:25", 25,
            "写论文", "", "论文", "t1",
        )
        self.assertEqual(Record.from_dict(record.to_dict()).task_id, "t1")

        legacy = Record.from_dict({
            "id": "r2", "date": DAY, "start": "", "end": "",
            "duration_min": 10, "title": "旧记录",
        })
        self.assertEqual(legacy.task_id, "")

    def test_store_tasks_roundtrip(self):
        store = Store(tasks=[_task("t1", "写论文", 0)])
        loaded = Store.from_dict(store.to_dict())
        self.assertEqual(len(loaded.tasks), 1)
        self.assertEqual(loaded.tasks[0].title, "写论文")


class TaskHelpersTest(unittest.TestCase):
    def test_sort_incomplete_by_priority_then_done(self):
        tasks = [
            _task("low", "低", 2),
            _task("done", "完成", 0, done=True),
            _task("high", "高", 0),
            _task("mid", "中", 1),
        ]
        self.assertEqual([t.id for t in sort_tasks(tasks)],
                         ["high", "mid", "low", "done"])

    def test_carry_over_only_unfinished_past(self):
        store = Store(tasks=[
            _task("old", "旧任务", day="2026-10-19"),
            _task("done", "已完成", done=True, day="2026-10-19"),
            _task("today", "今天", day=DAY),
            _task("future", "明天", day="2026-10-22"),
        ])
        moved = carry_over_unfinished(store, DAY)
        self.assertEqual(moved, 1)
        self.assertEqual(store.tasks[0].date, DAY)
        self.assertEqual(store.tasks[1].date, "2026-10-19")
        self.assertEqual(store.tasks[2].date, DAY)
        self.assertEqual(store.tasks[3].date, "2026-10-22")

    def test_today_tasks_sorted(self):
        store = Store(tasks=[
            _task("low", "低", 2),
            _task("high", "高", 0),
            _task("other", "别的日子", day="2026-10-20"),
        ])
        self.assertEqual([t.id for t in today_tasks(store, DAY)],
                         ["high", "low"])

    def test_task_minutes_sums_linked_records(self):
        records = [
            Record("r1", DAY, "", "", 25, task_id="t1"),
            Record("r2", DAY, "", "", 30, task_id="t1"),
            Record("r3", DAY, "", "", 60, task_id="t2"),
        ]
        self.assertEqual(task_minutes(records, "t1"), 55)
        self.assertEqual(task_minutes(records, "missing"), 0)


if __name__ == "__main__":
    unittest.main()
