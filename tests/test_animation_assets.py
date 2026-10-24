from __future__ import annotations

import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parent.parent
RESIDUE_TOOL = ROOT / "tools" / "suppress_green_residue.py"


class GreenResidueSuppressionTests(unittest.TestCase):
    def test_tool_keeps_chroma_background_and_preserves_alpha(self) -> None:
        source = RESIDUE_TOOL.read_text(encoding="utf-8")
        self.assertIn('exact_chroma = (r == 0) & (g == 255) & (b == 0)', source)
        self.assertIn("(alpha >= 8)", source)
        self.assertIn("(g >= minimum_spill)", source)
        self.assertIn("output[..., channel] = np.where(", source)
        self.assertIn("neutralize_highlight_green", source)
        self.assertIn('if image.mode == "RGB":', source)
        self.assertNotIn("output[..., 3] =", source)

    def test_tool_neutralizes_pixels_beyond_the_sprite_edge(self) -> None:
        source = RESIDUE_TOOL.read_text(encoding="utf-8")
        self.assertIn("spill * 32 >= max_red_or_blue", source)
        self.assertIn("luma * darken_factor", source)
        self.assertNotIn("bool edge", source)


if __name__ == "__main__":
    unittest.main()
