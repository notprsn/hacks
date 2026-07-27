import tempfile
import unittest
from pathlib import Path

from clean_whatsapp import clean_export, process_messages


class CleanWhatsAppTests(unittest.TestCase):
    def test_cleans_ios_export_and_preserves_multiline_body(self) -> None:
        export = (
            "Messages and calls are end-to-end encrypted.\n"
            "[24/07/2026, 14:03:12] Alice: first line\n"
            "second line\n"
            "[24/07/2026, 14:04:00] Bob: hello: still the body\n"
        )

        self.assertEqual(
            clean_export(export),
            ["first line\nsecond line", "hello: still the body"],
        )

    def test_cleans_android_export(self) -> None:
        export = (
            "24/07/26, 2:03 pm - Alice: one\n"
            "24/07/26, 2:04 pm - Bob: two\n"
        )

        self.assertEqual(clean_export(export), ["one", "two"])

    def test_writes_separator_and_final_newline(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            input_path = Path(directory) / "msgs.txt"
            output_path = Path(directory) / "cleaned.txt"
            input_path.write_text(
                "[24/07/2026, 14:03:12] Alice: one\n"
                "[24/07/2026, 14:04:00] Bob: two\n",
                encoding="utf-8",
            )

            count = process_messages(input_path, output_path)

            self.assertEqual(count, 2)
            self.assertEqual(
                output_path.read_text(encoding="utf-8"),
                "one\n\n----\n\ntwo\n",
            )


if __name__ == "__main__":
    unittest.main()
