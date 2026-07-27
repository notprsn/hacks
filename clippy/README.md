# 📎 Clippy

Pick the first and last lyric line you want. Clippy gives you an MP3 of exactly
that part of the song.

## Start here

1. Download [`clippy.zip`](https://notprsn.github.io/projects/clippy/downloads/clippy.zip)
   and unzip it.
2. Open the `clippy` folder.
3. Start Clippy:
   - **Mac:** double-click `start-clippy.command`
   - **Windows:** double-click `start-clippy.bat`
   - **Linux:** run `bash start-clippy.sh`

The first launch creates a private `.venv`, installs Clippy's dependencies, and
opens [the Clippy website](https://notprsn.github.io/projects/clippy/). Keep the
launcher window open while using Clippy. Later launches are faster.

Clippy needs Python 3.10 or newer. If the launcher says Python is missing,
install it from [python.org](https://www.python.org/downloads/) and run the
launcher again. FFmpeg is included automatically; no system setup is required.

## Use Clippy

1. Search for a song and choose a synced-lyrics result.
2. Click the first lyric line, then the last lyric line you want.
3. Click **✂️ cut it**, preview the clip, and download the MP3.

The first cut of a song downloads its audio. Later cuts use `.clippy_cache/` and
are faster. If Clippy finds the wrong recording, open **wrong recording?** and
paste the exact YouTube URL.

## Prefer Git?

Clone only the Clippy folder with Git's sparse checkout:

```bash
git clone --depth 1 --filter=blob:none --sparse https://github.com/notprsn/hacks.git
cd hacks
git sparse-checkout set clippy
cd clippy
```

Then run the launcher for your operating system.

## What runs where?

The interface is hosted at
[`notprsn.github.io/projects/clippy/`](https://notprsn.github.io/projects/clippy/).
The local `clippy.py` helper looks up synced lyrics through
[LRCLIB](https://lrclib.net), finds matching audio through `yt-dlp`, and cuts
the selected range with a private FFmpeg binary.

The helper listens only on `127.0.0.1`. Downloaded audio, cached songs, and
finished clips stay on your laptop.

Safari may block the hosted page from reaching the local helper. If that
happens, open the local interface shown in the launcher window:
`http://localhost:8765`.

## Manual start

The launchers are the supported setup path. After the first launch, the
equivalent manual command is:

```bash
.venv/bin/python clippy.py
```

On Windows, use `.venv\Scripts\python.exe clippy.py`.
