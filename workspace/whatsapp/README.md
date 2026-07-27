# WhatsApp export cleaner

This script turns a WhatsApp text export into message text without timestamps
or sender names. Multiline messages stay intact, and `----` separates adjacent
messages.

It recognizes the common iOS and Android export formats:

```text
[24/07/2026, 14:03:12] Person: Message
24/07/2026, 2:03 pm - Person: Message
```

## Run

```bash
cd workspace/whatsapp
python3 clean_whatsapp.py path/to/export.txt cleaned.txt
```

With no arguments, the script reads `msgs.txt` and writes
`cleaned_msgs.txt` in the current directory.

## Test

```bash
cd workspace/whatsapp
python3 -m unittest -v
```

Export files and cleaned output can contain private conversations, so the
repository ignores both default filenames.
