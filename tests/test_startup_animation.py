from __future__ import annotations

import importlib.util
import pathlib
import time
import unittest
from types import SimpleNamespace

import desktop_pet


ROOT = pathlib.Path(__file__).resolve().parent.parent


class FakePlayer:
    def __init__(self, active: bool = False) -> None:
        self.active = active
        self.calls = 0

    def play(self) -> bool:
        self.calls += 1
        self.active = True
        return True


class StartupDedupTests(unittest.TestCase):
    def test_active_animation_rejects_replay(self) -> None:
        player = FakePlayer(active=True)
        fake_pet = SimpleNamespace(
            _startup_animation=player,
            _last_startup_animation_started=0.0,
        )
        desktop_pet.Pet.play_startup_animation(fake_pet)
        self.assertEqual(player.calls, 0)

    def test_rapid_duplicate_is_cooled_down(self) -> None:
        player = FakePlayer(active=False)
        fake_pet = SimpleNamespace(
            _startup_animation=player,
            _last_startup_animation_started=time.monotonic() - 10,
        )
        desktop_pet.Pet.play_startup_animation(fake_pet)
        player.active = False
        desktop_pet.Pet.play_startup_animation(fake_pet)
        self.assertEqual(player.calls, 1)

    def test_tray_initial_sample_does_not_request_replay(self) -> None:
        path = ROOT / "pet-tray.py"
        spec = importlib.util.spec_from_file_location("pet_tray_under_test", path)
        assert spec is not None and spec.loader is not None
        tray = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tray)

        events: list[tuple[str, str | None]] = []
        sleeps = 0
        originals = (
            tray.codex_desktop_running,
            tray.call_control,
            tray.request_animation_replay,
            tray.time.sleep,
        )
        try:
            alive = [True, False, True]
            tray.codex_desktop_running = lambda: alive[min(sleeps, len(alive) - 1)]

            def fake_control(action: str) -> tuple[int, str]:
                events.append(("control", action))
                return 0, "ALREADY_RUNNING 123"

            tray.call_control = fake_control
            tray.request_animation_replay = lambda: events.append(("replay", None))

            def fake_sleep(_seconds: float) -> None:
                nonlocal sleeps
                sleeps += 1
                if sleeps >= 3:
                    raise StopIteration

            tray.time.sleep = fake_sleep
            with self.assertRaises(StopIteration):
                tray.codex_watch_worker()
        finally:
            (
                tray.codex_desktop_running,
                tray.call_control,
                tray.request_animation_replay,
                tray.time.sleep,
            ) = originals

        self.assertEqual(
            sum(1 for event in events if event[0] == "control"),
            2,
        )
        self.assertEqual(
            sum(1 for event in events if event[0] == "replay"),
            1,
        )


if __name__ == "__main__":
    unittest.main()
