# Spectrogram word

Generate an audible MP3 whose spectrogram spells a word, then render plots that
show the hidden text.

The generator maps horizontal text pixels to time and vertical text pixels to
frequency. It layers those tones over a quiet low-frequency drone and noise,
writes a WAV, and uses `ffmpeg` to encode the MP3. The renderer decodes an audio
file and produces full-range, word-band, and clean word-band PNGs.

## Requirements

- Python 3.10+
- `ffmpeg`
- The packages in `requirements.txt`

On macOS:

```bash
brew install ffmpeg
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

## Generate audio

From this directory:

```bash
python3 make_spectrogram_word_audio.py --word "hello"
```

The default output directory is `generated_audio/`. Useful controls include
`--duration`, `--min-freq`, `--max-freq`, `--tone-gain`, and `--seed`; run with
`--help` for the complete list.

## Render the spectrogram

```bash
python3 render_audio_spectrogram.py \
  generated_audio/hello_spectrogram_word.mp3
```

The default output directory is `spectrogram_renders/`.

## Included example

`examples/` contains the existing `amouromeoros` WAV, MP3, text mask, and three
spectrogram renders. Generated output outside that example is ignored by Git.
