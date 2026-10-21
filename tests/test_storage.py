# -*- coding: utf-8 -*-
"""存储层单元测试（往返、迁移、容错、导入校验）。"""

import csv
import json
import os
import tempfile
import unittest

from study_timer.models import Record, Store, ValidationError
from study_timer.storage import Repository


class RepositoryTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.mkdtemp()
        self.data_file = os.path.join(self.directory, "study_data.json")
        self.backup_file = os.path.join(self.directory, "study_data.bak.json")
        self.repo = Repository(self.data_file, self.backup_file)

    def test_empty_load(self):
        store = self.repo.load()
        self.assertEqual(store.records, [])
        self.assertEqual(store.settings.goal_min, 60)

    def test_roundtrip(self):
        store = Store()
        store.settings.goal_min = 90
        store.settings.theme = "dark"
        store.records.append(Record(
            "r1", "2026-10-20", "2026-10-20 10:00", "2026-10-20 10:30",
            30, "数学", "复习", "理科"))
        store.checkins.add("2026-10-20")
        self.repo.save(store)

        loaded = self.repo.load()
        self.assertEqual(loaded.settings.goal_min, 90)
        self.assertEqual(loaded.settings.theme, "dark")
        self.assertEqual(len(loaded.records), 1)
        self.assertEqual(loaded.records[0].tag, "理科")
        self.assertIn("2026-10-20", loaded.checkins)

    def test_migrate_v1(self):
        v1 = {
            "goal_min": 45,
            "remind": True,
            "remind_time": "20:00",
            "records": [{
                "id": "a",
                "date": "2026-10-01",
                "start": "2026-10-01 09:00",
                "end": "2026-10-01 09:30",
                "durationMin": 30,
                "title": "英语",
                "note": "",
            }],
            "checkins": {"2026-10-01": True},
        }
        with open(self.data_file, "w", encoding="utf-8") as fh:
            json.dump(v1, fh, ensure_ascii=False)

        store = self.repo.load()
        self.assertEqual(store.settings.goal_min, 45)
        self.assertTrue(store.settings.remind)
        self.assertEqual(store.records[0].duration_min, 30)
        self.assertEqual(store.records[0].tag, "")
        self.assertIn("2026-10-01", store.checkins)

    def test_corrupt_main_falls_back_to_backup(self):
        with open(self.backup_file, "w", encoding="utf-8") as fh:
            json.dump({"settings": {"goal_min": 30}, "records": [], "checkins": []}, fh)
        with open(self.data_file, "w", encoding="utf-8") as fh:
            fh.write("{ not json")

        store = self.repo.load()
        self.assertEqual(store.settings.goal_min, 30)

    def test_invalid_import(self):
        bad = os.path.join(self.directory, "bad.json")
        with open(bad, "w", encoding="utf-8") as fh:
            json.dump({"records": [{"date": "bad-date", "duration_min": 10}]}, fh)
        with self.assertRaises(ValidationError):
            self.repo.import_file(bad)

    def test_save_creates_backup(self):
        store = Store()
        self.repo.save(store)
        store.settings.goal_min = 100
        self.repo.save(store)
        self.assertTrue(os.path.exists(self.backup_file))

    def test_valid_load_not_marked_recovered(self):
        self.repo.save(Store())
        self.repo.load()
        self.assertFalse(self.repo.last_load_recovered)

    def test_accent_setting(self):
        from study_timer.models import Settings

        self.assertEqual(Settings.from_dict({}).accent, "blue")
        self.assertEqual(Settings.from_dict({"accent": "purple"}).accent, "purple")
        self.assertEqual(Settings.from_dict({"accent": "neon"}).accent, "blue")

    def test_break_settings_defaults_and_clamp(self):
        from study_timer.models import Settings

        settings = Settings.from_dict({})
        self.assertTrue(settings.auto_break)
        self.assertTrue(settings.ask_before_start)
        self.assertEqual(settings.short_break_min, 5)
        self.assertEqual(settings.long_break_min, 15)
        self.assertEqual(settings.rounds_per_long_break, 4)
        self.assertFalse(Settings.from_dict({"ask_before_start": False}).ask_before_start)

        clamped = Settings.from_dict({
            "short_break_min": 0,
            "long_break_min": 999,
            "rounds_per_long_break": 1,
        })
        self.assertEqual(clamped.short_break_min, 1)
        self.assertEqual(clamped.long_break_min, 120)
        self.assertEqual(clamped.rounds_per_long_break, 2)

    def test_csv_export(self):
        store = Store()
        store.records.append(Record(
            "r1", "2026-10-20", "2026-10-20 09:00", "2026-10-20 09:45",
            45, "线性代数", "第三章", "数学"))
        store.records.append(Record(
            "r2", "2026-10-19", "2026-10-19 20:00", "2026-10-19 20:25",
            25, "英语阅读", "", "英语"))

        path = os.path.join(self.directory, "out.csv")
        self.repo.export_csv(store, path)

        with open(path, "r", encoding="utf-8-sig", newline="") as fh:
            rows = list(csv.reader(fh))

        self.assertEqual(rows[0], ["日期", "开始", "结束", "时长(分钟)", "学习内容", "标签", "备注"])
        self.assertEqual(len(rows), 3)
        # 按日期升序：10-19 在前
        self.assertEqual(rows[1][0], "2026-10-19")
        self.assertEqual(rows[1][4], "英语阅读")
        self.assertEqual(rows[2][4], "线性代数")
        self.assertEqual(rows[2][3], "45")

    def test_csv_export_empty(self):
        path = os.path.join(self.directory, "empty.csv")
        self.repo.export_csv(Store(), path)
        with open(path, "r", encoding="utf-8-sig", newline="") as fh:
            rows = list(csv.reader(fh))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][0], "日期")

    def test_rotating_backups_keep_seven(self):
        store = Store()
        store.settings.goal_min = 1
        self.repo.save(store)  # 首次保存，没有旧文件可备份

        for goal in range(2, 12):
            store.settings.goal_min = goal
            self.repo.save(store)

        backups = self.repo.list_backups()
        self.assertEqual(len(backups), 7)
        # 最新一份备份应是倒数第二次保存（goal=10）
        with open(backups[0], "r", encoding="utf-8") as fh:
            data = json.load(fh)
        self.assertEqual(data["settings"]["goal_min"], 10)

    def test_recover_from_rotating_backup(self):
        store = Store()
        store.settings.goal_min = 42
        self.repo.save(store)

        store.settings.goal_min = 99
        self.repo.save(store)  # 同时生成 .bak 与轮转备份（内容为 goal=42）

        # 删除单份备份，强制走轮转备份
        if os.path.exists(self.backup_file):
            os.remove(self.backup_file)
        with open(self.data_file, "w", encoding="utf-8") as fh:
            fh.write("{ broken")

        loaded = self.repo.load()
        self.assertTrue(self.repo.last_load_recovered)
        self.assertEqual(loaded.settings.goal_min, 42)


if __name__ == "__main__":
    unittest.main()
