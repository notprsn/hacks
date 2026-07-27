import os
import subprocess
import tempfile
import unittest
from pathlib import Path

import clippy


class ClippyTests(unittest.TestCase):
    def test_cut_has_exact_requested_duration(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.wav"
            subprocess.run(
                [
                    clippy.FFMPEG,
                    "-y",
                    "-v",
                    "error",
                    "-f",
                    "lavfi",
                    "-i",
                    "sine=frequency=440:duration=3",
                    str(source),
                ],
                check=True,
            )

            output = clippy.cut_to_mp3(str(source), 0.5, 2.0, fade=False)
            try:
                decoded = subprocess.run(
                    [
                        clippy.FFMPEG,
                        "-v",
                        "error",
                        "-i",
                        output,
                        "-f",
                        "f32le",
                        "-ac",
                        "1",
                        "-ar",
                        "44100",
                        "-",
                    ],
                    capture_output=True,
                )
                self.assertEqual(decoded.returncode, 0, decoded.stderr.decode())
                duration = len(decoded.stdout) / (4 * 44_100)
                self.assertAlmostEqual(duration, 1.5, places=2)
            finally:
                os.remove(output)

    def test_clip_rejects_backwards_range(self) -> None:
        with self.assertRaisesRegex(clippy.ClipError, "before the start"):
            clippy.cut_to_mp3("unused", 2.0, 1.0)

    def test_safe_filename_removes_reserved_characters(self) -> None:
        self.assertEqual(clippy._safe('A/B: "Song"?'), "A B Song")


if __name__ == "__main__":
    unittest.main()
