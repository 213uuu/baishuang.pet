from __future__ import annotations

import pathlib
import time
import unittest

import desktop_pet


ROOT = pathlib.Path(__file__).resolve().parent.parent


class GameLoopPriorityTests(unittest.TestCase):
    def setUp(self) -> None:
        desktop_pet.register_bubble_font()
        self.pet = desktop_pet.Pet(ROOT / "frames", debug=False)
        self.pet.root.withdraw()
        self.pet._alive = True
        self.pet._next_alive_check = time.time() + 999
        self.pet._next_topmost = time.time() + 999
        self.pet._next_work_check = 0
        self.pet._next_extra_idle_check = time.time() + 999
        self.pet.codex_working = lambda: True
        self.pet.dsh_working = lambda: False
        self.pet.codex_alive = lambda: True

    def tearDown(self) -> None:
        self.pet._startup_animation.close(notify=False)
        self.pet.root.destroy()

    def _start_gaming_with_pending_work(self) -> None:
        self.pet.set_state("idle")
        self.pet.was_working = True
        self.pet._working = True
        self.pet._codex_working = True
        self.pet._dsh_working = False
        self.pet._dual_work_active = False
        self.pet._work_entry_pending = "normal"
        self.pet.play_extra_action("gaming", show_action_bubble=False)
        self.assertEqual(self.pet.state, "anim-game-intro")
        self.assertIsNone(self.pet._work_entry_pending)

    def test_game_intro_enters_repeating_loop_despite_pending_work(self) -> None:
        self._start_gaming_with_pending_work()
        self.pet.frame_index = len(self.pet.frames(self.pet.state)) - 1
        self.pet._tick_body()
        self.assertEqual(self.pet.state, "anim-game-loop")
        self.assertFalse(self.pet.play_once)

    def test_pending_work_does_not_interrupt_game_loop(self) -> None:
        self._start_gaming_with_pending_work()
        self.pet.frame_index = len(self.pet.frames(self.pet.state)) - 1
        self.pet._tick_body()
        self.pet._work_entry_pending = "normal"
        self.pet._work_entry_pending_at = time.time() - 1
        self.pet._next_work_check = time.time() + 999
        self.pet.frame_index = len(self.pet.frames(self.pet.state)) - 1
        self.pet._tick_body()
        self.assertEqual(self.pet.state, "anim-game-loop")
        self.assertFalse(self.pet.play_once)


if __name__ == "__main__":
    unittest.main()
