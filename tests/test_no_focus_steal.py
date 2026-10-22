from __future__ import annotations

import importlib.util
import inspect
import pathlib
import unittest
from types import SimpleNamespace

import desktop_pet


ROOT = pathlib.Path(__file__).resolve().parent.parent


class _RootWithoutLift:
    def lift(self) -> None:
        raise AssertionError("root.lift() must not be used for routine updates")


class NoFocusStealTests(unittest.TestCase):
    def test_balance_busy_path_does_not_lift_root(self) -> None:
        fake_pet = SimpleNamespace(
            _set_topmost=lambda _topmost: None,
            root=_RootWithoutLift(),
            _balance_busy=True,
            say=lambda *_args, **_kwargs: None,
        )
        desktop_pet.Pet.show_balance(fake_pet)

    def test_window_menus_restore_foreground_after_focus(self) -> None:
        for method in (
            desktop_pet.Pet._on_menu,
            desktop_pet.Pet._open_mode_selector,
        ):
            source = inspect.getsource(method)
            with self.subTest(method=method.__name__):
                self.assertIn("focus_force", source)
        class_source = inspect.getsource(desktop_pet.Pet)
        self.assertIn("restore_foreground(previous)", class_source)

    def test_startup_player_does_not_lift_window(self) -> None:
        source = inspect.getsource(desktop_pet.StartupAnimationPlayer.play)
        self.assertNotIn(".lift(", source)

    def test_periodic_topmost_reassert_is_non_activating(self) -> None:
        source = inspect.getsource(desktop_pet.Pet._set_topmost)
        self.assertIn("0x0002 | 0x0001 | 0x0010", source)

    def test_tray_menu_restores_previous_foreground(self) -> None:
        path = ROOT / "pet-tray.py"
        spec = importlib.util.spec_from_file_location("pet_tray_focus_test", path)
        assert spec is not None and spec.loader is not None
        tray = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tray)
        source = inspect.getsource(tray.show_menu)
        self.assertIn("previous_foreground", source)
        self.assertIn("SetForegroundWindow(previous_foreground)", source)


if __name__ == "__main__":
    unittest.main()
