# -*- coding: utf-8 -*-
"""数据模型与校验。

内部统一使用 snake_case 字段；兼容读取 v1 的 `durationMin` 与平铺 settings，
保存时统一写为 v2 结构。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
import uuid

from .config import (
    DEFAULT_FOCUS,
    DEFAULT_GOAL,
    DEFAULT_LONG_BREAK,
    DEFAULT_ROUNDS_PER_LONG,
    DEFAULT_SHORT_BREAK,
    FOCUS_PRESETS,
    SCHEMA_VERSION,
)


class ValidationError(ValueError):
    """数据格式不合法。"""


def _as_str(value, default=""):
    if value is None:
        return default
    return str(value)


def _parse_date(value) -> str:
    text = _as_str(value).strip()
    try:
        datetime.strptime(text, "%Y-%m-%d")
    except Exception:
        raise ValidationError(f"日期格式应为 YYYY-MM-DD：{text!r}")
    return text


def _parse_duration(value) -> int:
    try:
        minutes = int(value)
    except Exception:
        raise ValidationError("学习时长必须是整数分钟")
    if minutes <= 0:
        raise ValidationError("学习时长必须大于 0")
    return minutes


def _parse_int(value, default: int, minimum: int, maximum: int) -> int:
    """解析整数并夹到合理区间；非法值回退默认。"""
    try:
        number = int(value)
    except Exception:
        return default
    return max(minimum, min(maximum, number))


def _parse_flag(value, default: bool = True) -> bool:
    """解析布尔开关：缺失时用默认值，兼容 JSON 布尔与常见字符串写法。"""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = _as_str(value).strip().lower()
    if not text:
        return default
    return text not in ("0", "false", "no", "off")


@dataclass
class Record:
    """一条学习记录。"""

    id: str
    date: str            # YYYY-MM-DD
    start: str           # YYYY-MM-DD HH:MM
    end: str             # YYYY-MM-DD HH:MM
    duration_min: int
    title: str = ""
    note: str = ""
    tag: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> "Record":
        if not isinstance(data, dict):
            raise ValidationError("单条记录必须是对象")
        # 兼容 v1 字段名 durationMin
        raw_duration = data.get("duration_min", data.get("durationMin"))
        return cls(
            id=_as_str(data.get("id")) or str(uuid.uuid4()),
            date=_parse_date(data.get("date")),
            start=_as_str(data.get("start")),
            end=_as_str(data.get("end")),
            duration_min=_parse_duration(raw_duration),
            title=_as_str(data.get("title")),
            note=_as_str(data.get("note")),
            tag=_as_str(data.get("tag")),
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "date": self.date,
            "start": self.start,
            "end": self.end,
            "duration_min": self.duration_min,
            "title": self.title,
            "note": self.note,
            "tag": self.tag,
        }


@dataclass
class Settings:
    """用户设置与提醒去重状态。"""

    goal_min: int = DEFAULT_GOAL
    remind: bool = False
    remind_time: str = "21:00"
    focus_preset: int = DEFAULT_FOCUS
    theme: str = "light"
    hotkey_enabled: bool = True
    auto_break: bool = True
    short_break_min: int = DEFAULT_SHORT_BREAK
    long_break_min: int = DEFAULT_LONG_BREAK
    rounds_per_long_break: int = DEFAULT_ROUNDS_PER_LONG
    last_remind_date: str = ""
    last_goal_date: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> "Settings":
        data = data or {}
        try:
            goal = int(data.get("goal_min", DEFAULT_GOAL))
        except Exception:
            goal = DEFAULT_GOAL
        if goal <= 0:
            goal = DEFAULT_GOAL

        theme = _as_str(data.get("theme"), "light")
        if theme not in ("light", "dark"):
            theme = "light"

        try:
            preset = int(data.get("focus_preset", DEFAULT_FOCUS))
        except Exception:
            preset = DEFAULT_FOCUS
        if preset not in FOCUS_PRESETS:
            preset = DEFAULT_FOCUS

        remind_time = _as_str(data.get("remind_time"), "21:00") or "21:00"
        try:
            datetime.strptime(remind_time, "%H:%M")
        except Exception:
            remind_time = "21:00"

        return cls(
            goal_min=goal,
            remind=bool(data.get("remind", False)),
            remind_time=remind_time,
            focus_preset=preset,
            theme=theme,
            hotkey_enabled=_parse_flag(data.get("hotkey_enabled"), True),
            auto_break=_parse_flag(data.get("auto_break"), True),
            short_break_min=_parse_int(
                data.get("short_break_min"), DEFAULT_SHORT_BREAK, 1, 60),
            long_break_min=_parse_int(
                data.get("long_break_min"), DEFAULT_LONG_BREAK, 1, 120),
            rounds_per_long_break=_parse_int(
                data.get("rounds_per_long_break"), DEFAULT_ROUNDS_PER_LONG, 2, 12),
            last_remind_date=_as_str(data.get("last_remind_date")),
            last_goal_date=_as_str(data.get("last_goal_date")),
        )

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Store:
    """整个应用的数据快照。"""

    version: int = SCHEMA_VERSION
    settings: Settings = field(default_factory=Settings)
    records: list = field(default_factory=list)
    checkins: set = field(default_factory=set)

    def tags(self):
        """已使用的标签（去重排序）。"""
        return sorted({r.tag.strip() for r in self.records if r.tag and r.tag.strip()})

    def to_dict(self) -> dict:
        return {
            "version": SCHEMA_VERSION,
            "settings": self.settings.to_dict(),
            "records": [r.to_dict() for r in self.records],
            "checkins": sorted(self.checkins),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Store":
        if not isinstance(data, dict):
            raise ValidationError("数据文件根节点必须是对象")

        # settings：v2 为嵌套对象；v1 为平铺字段
        if isinstance(data.get("settings"), dict):
            settings = Settings.from_dict(data["settings"])
        else:
            settings = Settings.from_dict(data)

        raw_records = data.get("records", [])
        if raw_records is None:
            raw_records = []
        if not isinstance(raw_records, list):
            raise ValidationError("records 必须是数组")
        records = [Record.from_dict(item) for item in raw_records]

        raw_checkins = data.get("checkins", [])
        if isinstance(raw_checkins, dict):
            checkins = {str(k) for k, v in raw_checkins.items() if v}
        elif isinstance(raw_checkins, list):
            checkins = {str(item) for item in raw_checkins}
        else:
            checkins = set()

        # 有记录即视为当天打卡，保证数据自洽
        for record in records:
            checkins.add(record.date)

        return cls(version=SCHEMA_VERSION, settings=settings, records=records, checkins=checkins)
