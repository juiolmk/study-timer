# -*- coding: utf-8 -*-
"""主题与强调色测试。"""

import unittest

from study_timer.ui.theme import ACCENTS, Theme


class ThemeTest(unittest.TestCase):
    def test_all_accents_light(self):
        for key, meta in ACCENTS.items():
            self.assertEqual(Theme("light", key).p.primary, meta["light"])

    def test_all_accents_dark(self):
        for key, meta in ACCENTS.items():
            self.assertEqual(Theme("dark", key).p.primary, meta["dark"])

    def test_invalid_accent_falls_back_to_blue(self):
        theme = Theme("light", "neon")
        self.assertEqual(theme.accent, "blue")
        self.assertEqual(theme.p.primary, ACCENTS["blue"]["light"])

    def test_invalid_theme_falls_back_to_light(self):
        theme = Theme("sepia", "green")
        self.assertEqual(theme.name, "light")
        self.assertEqual(theme.p.primary, ACCENTS["green"]["light"])


if __name__ == "__main__":
    unittest.main()
