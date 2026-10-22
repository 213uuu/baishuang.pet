from __future__ import annotations

import os
import pathlib
import sqlite3
import tempfile
import time
import unittest
from types import SimpleNamespace

import desktop_pet as pet


ROOT = pathlib.Path(__file__).resolve().parent.parent


class BalanceTests(unittest.TestCase):
    def test_deepseek_balance_payload(self) -> None:
        payload = {
            "balance_infos": [
                {
                    "currency": "CNY",
                    "total_balance": "12.34",
                    "granted_balance": "0.00",
                    "topped_up_balance": "12.34",
                }
            ]
        }
        self.assertEqual(
            pet.Pet.format_balance(payload),
            "余额 12.34 CNY（充值 12.34 / 赠金 0.00）",
        )

    def test_empty_balance_payload(self) -> None:
        self.assertEqual(
            pet.Pet.format_balance({"balance_infos": []}),
            "接口通了，但没有余额数据。",
        )


class WorkDetectionTests(unittest.TestCase):
    def test_dsh_session_write_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = pathlib.Path(temporary)
            session = (
                home
                / "sessions"
                / "workspace"
                / "session-test"
                / "session.v4.jsonl.zstd"
            )
            session.parent.mkdir(parents=True)
            session.write_bytes(b"test")
            dummy = SimpleNamespace(
                _dsh_working=False,
                dsh_home=lambda: home,
            )
            self.assertTrue(pet.Pet.dsh_working(dummy))

    def test_codex_log_activity_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = pathlib.Path(temporary)
            database = home / "logs_2.sqlite"
            connection = sqlite3.connect(database)
            connection.execute(
                """
                CREATE TABLE logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts INTEGER,
                    target TEXT
                )
                """
            )
            connection.execute(
                "INSERT INTO logs(ts, target) VALUES(?, ?)",
                (int(time.time()), "codex_core::stream_events_utils"),
            )
            connection.commit()
            connection.close()
            dummy = SimpleNamespace(codex_home=lambda: home)
            age = time.time() - pet.Pet.codex_log_activity(dummy)
            self.assertGreaterEqual(age, 0)
            self.assertLess(age, 5)


class BubbleTests(unittest.TestCase):
    def test_text_rectangle_is_inside_cloud(self) -> None:
        self.assertTrue(
            pet.bubble_contains_text_rect(
                420,
                166,
                290,
                64,
                clearance=7,
            )
        )

    def test_wide_multiline_text_remains_inside_cloud(self) -> None:
        self.assertTrue(
            pet.bubble_contains_text_rect(
                416,
                166,
                362,
                96,
                clearance=7,
            )
        )

    def test_bubble_wraps_near_full_canvas_width(self) -> None:
        self.assertGreaterEqual(pet.BUBBLE_MAX_TEXT_WIDTH_RATIO, 0.85)
        self.assertLessEqual(pet.BUBBLE_WRAP_STEP_PX, 6)


class RuntimeAssetTests(unittest.TestCase):
    def test_required_runtime_assets_exist(self) -> None:
        required = [
            ROOT / "desktop_pet.py",
            ROOT / "bubble_shape.py",
            ROOT / "assets" / "baishuang.ico",
            ROOT / "frames" / "idle" / "00.png",
            ROOT / "frames" / "anim-work-start" / "000.png",
            ROOT / "frames" / "anim-work-intro" / "000.png",
            ROOT / "frames" / "anim-work-hold" / "000.png",
            ROOT / "startup-animation" / "frames" / "frame_0001.png",
            ROOT / "fonts" / "Yozai-0.868" / "Yozai-Regular.ttf",
            ROOT / "fonts" / "Yozai-0.868" / "OFL.txt",
        ]
        for path in required:
            with self.subTest(path=path):
                self.assertTrue(path.is_file(), path)

    def test_private_runtime_files_are_not_packaged(self) -> None:
        ignore_rules = (ROOT / ".gitignore").read_text(encoding="utf-8")
        for pattern in ("auth.json", ".env", "pet.pid", "pet.log", "pet-mode.txt"):
            with self.subTest(pattern=pattern):
                self.assertIn(pattern, ignore_rules)

    def test_disabled_shy_b_remains_disabled(self) -> None:
        self.assertIn("shy_b", pet.DISABLED_EXTRA_ACTIONS)


if __name__ == "__main__":
    unittest.main()
