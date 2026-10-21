# -*- coding: utf-8 -*-
"""静态资源与打包元数据回归测试。

覆盖三件事：

1. ``resource_path`` 在源码运行下解析到项目根（打包后走 ``sys._MEIPASS``，
   该分支用 mock 模拟，避免依赖真实打包产物）；
2. ``assets/study_timer.ico`` 入库、是合法 ICO，且包含全部目标尺寸；
3. ``version_info.txt`` 存在，且版本号与 ``config.VERSION`` 保持一致。
"""

import struct
import unittest
from pathlib import Path
from unittest import mock

from study_timer import config, resources
from study_timer.resources import resource_path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ICON_RELATIVE = "assets/study_timer.ico"
#: 期望图标包含的尺寸（Windows 任务栏 / 资源管理器 / 高 DPI 各自挑一档）
EXPECTED_SIZES = (16, 24, 32, 48, 64, 128, 256)


def _parse_ico_entries(data: bytes):
    """解析 ICO 目录项，返回 ``[{'width', 'height', 'bpp', 'bytes', 'offset'}]``。"""
    reserved, kind, count = struct.unpack_from("<HHH", data, 0)
    assert reserved == 0 and kind == 1, "不是合法 ICO 文件"
    entries = []
    for index in range(count):
        width, height, _colors, _reserved, _planes, bpp, length, offset = struct.unpack_from(
            "<BBBBHHII", data, 6 + 16 * index)
        entries.append({
            "width": width or 256,
            "height": height or 256,
            "bpp": bpp,
            "bytes": length,
            "offset": offset,
        })
    return entries


class ResourcePathTest(unittest.TestCase):
    """资源路径解析。"""

    def test_source_tree_falls_back_to_project_root(self):
        path = Path(resource_path("app.py"))
        self.assertTrue(path.is_file())
        self.assertEqual(path.parent.resolve(), PROJECT_ROOT)

    def test_empty_relative_returns_base_dir(self):
        self.assertEqual(Path(resource_path("")).resolve(), PROJECT_ROOT)

    def test_windows_separator_is_normalized(self):
        self.assertEqual(
            resource_path("assets\\study_timer.ico"),
            resource_path(ICON_RELATIVE),
        )

    def test_meipass_takes_priority_when_frozen(self):
        """打包后（存在 sys._MEIPASS）应优先使用解包目录。"""
        bundle = str(PROJECT_ROOT / "dist")
        with mock.patch.object(resources.sys, "_MEIPASS", bundle, create=True):
            resolved = resource_path(ICON_RELATIVE)
        self.assertEqual(resolved, str(Path(bundle) / ICON_RELATIVE))

    def test_resource_exists_matches_filesystem(self):
        self.assertTrue(resources.resource_exists(ICON_RELATIVE))
        self.assertFalse(resources.resource_exists("assets/__missing__.ico"))


class IconAssetTest(unittest.TestCase):
    """应用图标文件本身。"""

    def setUp(self):
        self.icon = Path(resource_path(ICON_RELATIVE))
        self.data = self.icon.read_bytes()

    def test_icon_exists(self):
        self.assertTrue(self.icon.is_file(), f"图标未入库：{self.icon}")
        self.assertGreater(len(self.data), 512)

    def test_ico_magic_header(self):
        self.assertEqual(self.data[:4], b"\x00\x00\x01\x00")

    def test_contains_all_sizes(self):
        entries = _parse_ico_entries(self.data)
        sizes = {(entry["width"], entry["height"]) for entry in entries}
        for size in EXPECTED_SIZES:
            self.assertIn((size, size), sizes, f"缺少 {size}x{size}")
        self.assertEqual(len(entries), len(EXPECTED_SIZES))

    def test_entries_are_32bit_and_in_bounds(self):
        entries = _parse_ico_entries(self.data)
        total = len(self.data)
        for entry in entries:
            label = f"{entry['width']}x{entry['height']}"
            self.assertEqual(entry["bpp"], 32, f"{label} 不是 32 位")
            self.assertGreater(entry["bytes"], 0, f"{label} 帧为空")
            self.assertLessEqual(entry["offset"] + entry["bytes"], total,
                                 f"{label} 帧越界")

    def test_frames_are_png(self):
        entries = _parse_ico_entries(self.data)
        for entry in entries:
            payload = self.data[entry["offset"]:entry["offset"] + 8]
            self.assertEqual(payload, b"\x89PNG\r\n\x1a\n",
                             f"{entry['width']}x{entry['height']} 帧不是 PNG")


class VersionInfoTest(unittest.TestCase):
    """PyInstaller 版本资源模板。"""

    def setUp(self):
        self.path = PROJECT_ROOT / "version_info.txt"

    def test_version_info_exists(self):
        self.assertTrue(self.path.is_file(), "缺少 version_info.txt")

    def test_version_matches_config(self):
        text = self.path.read_text(encoding="utf-8")
        parts = [int(piece) for piece in config.VERSION.split(".")[:3]]
        while len(parts) < 3:
            parts.append(0)
        major, minor, patch = parts

        self.assertIn(f"filevers=({major}, {minor}, {patch}, 0)", text)
        self.assertIn(f"prodvers=({major}, {minor}, {patch}, 0)", text)
        self.assertIn(f"FileVersion', '{major}.{minor}.{patch}.0'", text)
        self.assertIn(f"ProductVersion', '{major}.{minor}.{patch}.0'", text)

    def test_metadata_fields_present(self):
        text = self.path.read_text(encoding="utf-8")
        for expected in (
            "'CompanyName', 'StudyTimer'",
            "'InternalName', 'StudyTimer'",
            "'ProductName', '学习打卡'",
            "'OriginalFilename', '学习打卡.exe'",
            "'FileDescription', '学习打卡 - 学习计时与习惯记录'",
        ):
            self.assertIn(expected, text)
        # 2052 = 简体中文，1200 = Unicode 代码页；StringTable 键是 080404b0
        self.assertIn("VarStruct('Translation', [2052, 1200])", text)
        self.assertIn("'080404b0'", text)


if __name__ == "__main__":
    unittest.main()
