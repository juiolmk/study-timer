# -*- coding: utf-8 -*-
"""任务辅助：排序、创建、跨日顺延与时长汇总。"""

from __future__ import annotations

from datetime import date, datetime
import uuid

from .models import Store, Task

#: 优先级：0 高 / 1 中 / 2 低
PRIORITY_LABELS = ("高", "中", "低")


def create_task(title: str, priority: int = 1, tag: str = "",
                day: str | None = None) -> Task:
    """创建一条今日任务。"""
    title = (title or "").strip()
    if not title:
        raise ValueError("任务标题不能为空")
    try:
        priority = int(priority)
    except Exception:
        priority = 1
    return Task(
        id=uuid.uuid4().hex,
        date=day or date.today().isoformat(),
        title=title,
        priority=max(0, min(2, priority)),
        tag=(tag or "").strip(),
        created_at=datetime.now().isoformat(timespec="seconds"),
    )


def sort_tasks(tasks) -> list:
    """未完成在前、按优先级从高到低；已完成沉底。"""
    return sorted(
        tasks,
        key=lambda t: (1 if t.done else 0, t.priority, t.created_at, t.id),
    )


def today_tasks(store: Store, day: str | None = None) -> list:
    """返回某天（默认今天）的任务，已排序。"""
    day = day or date.today().isoformat()
    return sort_tasks([task for task in store.tasks if task.date == day])


def task_minutes(records, task_id: str) -> int:
    """任务累计学习分钟数（由记录实时汇总）。"""
    return sum(int(record.duration_min) for record in records
               if record.task_id == task_id)


def carry_over_unfinished(store: Store, today: str | None = None) -> int:
    """把之前未完成的任务顺延到今天，返回顺延条数。"""
    today = today or date.today().isoformat()
    moved = 0
    for task in store.tasks:
        if not task.done and task.date < today:
            task.date = today
            moved += 1
    return moved
