from __future__ import annotations

import pathlib
import unittest

try:
    import numpy as np
    from PIL import Image

    from tools.suppress_green_residue import suppress_green_residue
    from tools.recolor_runtime_key import recolor_runtime_key
except ModuleNotFoundError as exc:
    raise unittest.SkipTest(
        f"image regression tests require Pillow and NumPy: {exc}"
    ) from exc


ROOT = pathlib.Path(__file__).resolve().parent.parent
FRAMES_ROOT = ROOT / "frames"


class GreenEdgeCleanupTests(unittest.TestCase):
    def test_subtle_green_cast_is_removed_from_translucent_silhouette(self) -> None:
        image = Image.new("RGBA", (9, 9), (0, 0, 0, 0))
        pixels = np.asarray(image).copy()
        pixels[3:6, 3:6, :3] = 180
        pixels[3:6, 3:6, 3] = 150
        pixels[3, 4] = (220, 225, 219, 110)
        image = Image.fromarray(pixels, mode="RGBA")

        processed, changed = suppress_green_residue(
            image,
            darken_factor=0.32,
            minimum_spill=4,
        )

        result = np.asarray(processed)
        self.assertGreater(changed, 0)
        self.assertEqual(int(result[3, 4, 3]), 110)
        self.assertLessEqual(int(result[3, 4, 1]), max(
            int(result[3, 4, 0]),
            int(result[3, 4, 2]),
        ))
        second_pass, second_changed = suppress_green_residue(
            processed,
            darken_factor=0.32,
            minimum_spill=4,
        )
        self.assertEqual(second_changed, 0)
        np.testing.assert_array_equal(np.asarray(second_pass), result)

    def test_opaque_scene_without_background_does_not_treat_image_border_as_silhouette(self) -> None:
        pixels = np.full((9, 9, 3), 220, dtype=np.uint8)
        pixels[:, :, 1] = 225
        image = Image.fromarray(pixels, mode="RGB")

        processed, _ = suppress_green_residue(
            image,
            darken_factor=0.32,
            minimum_spill=4,
        )

        np.testing.assert_array_equal(np.asarray(processed), pixels)

    def test_runtime_key_recolors_exact_green_without_touching_alpha(self) -> None:
        image = Image.new("RGBA", (3, 1), (0, 255, 0, 255))
        image.putpixel((1, 0), (20, 30, 40, 255))
        image.putpixel((2, 0), (0, 255, 0, 0))

        processed, changed = recolor_runtime_key(image)
        result = np.asarray(processed)

        self.assertEqual(changed, 2)
        np.testing.assert_array_equal(result[0, 0], [17, 7, 3, 255])
        np.testing.assert_array_equal(result[0, 1], [20, 30, 40, 255])
        np.testing.assert_array_equal(result[0, 2], [17, 7, 3, 0])

    def test_tk_uses_the_non_green_runtime_key(self) -> None:
        source = (ROOT / "desktop_pet.py").read_text(encoding="utf-8")
        self.assertIn('CHROMA = "#110703"', source)

    def test_animation_mode_silhouettes_have_no_green_fringe(self) -> None:
        green_edge_pixels = 0
        worst = ("", 0, 0, 0)
        for directory in sorted(FRAMES_ROOT.glob("anim-*")):
            for path in sorted(directory.glob("*.png")):
                pixels = np.asarray(Image.open(path).convert("RGBA"), dtype=np.int16)
                red = pixels[..., 0]
                green = pixels[..., 1]
                blue = pixels[..., 2]
                alpha = pixels[..., 3]
                exact_chroma = (red == 0) & (green == 255) & (blue == 0)
                background = (alpha <= 8) | exact_chroma
                padded = np.pad(background, 1, constant_values=True)
                near_background = np.zeros_like(background)
                for row_offset in range(3):
                    for column_offset in range(3):
                        if row_offset == 1 and column_offset == 1:
                            continue
                        near_background |= padded[
                            row_offset:row_offset + background.shape[0],
                            column_offset:column_offset + background.shape[1],
                        ]
                boundary = ~background & near_background
                spill = green - np.maximum(red, blue)
                count = int(np.count_nonzero(boundary & (spill > 0)))
                green_edge_pixels += count
                if count and spill.max() > worst[1]:
                    worst = (
                        str(path.relative_to(FRAMES_ROOT)),
                        int(spill.max()),
                        int(count),
                        int(alpha[boundary & (spill > 0)].max()),
                    )

        self.assertEqual(
            green_edge_pixels,
            0,
            f"animation-mode green silhouette pixels={green_edge_pixels}, worst={worst}",
        )


if __name__ == "__main__":
    unittest.main()
