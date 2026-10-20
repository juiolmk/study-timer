# -*- coding: utf-8 -*-
"""存储层单元测试（往返、迁移、容错、导入校验）。"""

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


if __name__ == "__main__":
    unittest.main()
