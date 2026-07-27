#!/usr/bin/env python3
"""Create audio whose spectrogram spells a word.

This generates a WAV first, then encodes it to MP3 with ffmpeg. The word is
drawn as a mask where horizontal position maps to time and vertical position
maps to frequency.
"""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from scipy import signal
from scipy.io import wavfile


FONT_CANDIDATES = (
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/System/Library/Fonts/Supplemental/Verdana Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
)


def load_font(word: str, width: int, height: int) -> ImageFont.ImageFont:
    """Find the largest available font that fits the spectrogram mask."""
    font_path = next((path for path in FONT_CANDIDATES if Path(path).exists()), None)
    if font_path is None:
        return ImageFont.load_default()

    test_image = Image.new("L", (width, height), 255)
    draw = ImageDraw.Draw(test_image)
    max_width = int(width * 0.94)
    max_height = int(height * 0.70)

    for size in range(height, 10, -2):
        font = ImageFont.truetype(font_path, size)
        left, top, right, bottom = draw.textbbox((0, 0), word, font=font)
        if right - left <= max_width and bottom - top <= max_height:
            return font

    return ImageFont.truetype(font_path, 12)


def render_word_mask(word: str, width: int, height: int) -> Image.Image:
    """Render black text on white background for spectrogram synthesis."""
    image = Image.new("L", (width, height), 255)
    draw = ImageDraw.Draw(image)
    font = load_font(word, width, height)
    left, top, right, bottom = draw.textbbox((0, 0), word, font=font)
    text_width = right - left
    text_height = bottom - top
    x = (width - text_width) // 2 - left
    y = (height - text_height) // 2 - top
    draw.text((x, y), word, fill=0, font=font)

    # A tiny blur thickens anti-aliased edges into smoother tones.
    image = image.filter(ImageFilter.GaussianBlur(radius=0.45))
    return image


def smooth_window(length: int) -> np.ndarray:
    if length <= 2:
        return np.ones(length, dtype=np.float32)
    window = np.hanning(length).astype(np.float32)
    return np.maximum(window, 0.05)


def add_word_tones(
    audio: np.ndarray,
    mask: np.ndarray,
    *,
    sample_rate: int,
    duration: float,
    min_freq: float,
    max_freq: float,
    gain: float,
    row_step: int,
) -> None:
    """Add sine tones for dark pixels in the word mask."""
    height, width = mask.shape
    column_duration = duration / width

    for col in range(width):
        start = int(col * column_duration * sample_rate)
        end = int((col + 1) * column_duration * sample_rate)
        if end <= start:
            continue

        rows = np.where(mask[:, col])[0][::row_step]
        if rows.size == 0:
            continue

        t = np.arange(end - start, dtype=np.float32) / sample_rate
        window = smooth_window(t.size)
        slice_audio = np.zeros_like(t)

        for row in rows:
            position = row / max(height - 1, 1)
            frequency = max_freq - position * (max_freq - min_freq)
            slice_audio += np.sin(2.0 * np.pi * frequency * t)

        slice_audio *= gain * window / max(np.sqrt(rows.size), 1.0)
        audio[start:end] += slice_audio


def add_audible_background(
    audio: np.ndarray,
    *,
    sample_rate: int,
    seed: int,
    noise_gain: float,
    drone_gain: float,
) -> None:
    """Add background sound that should not cover the text band too much."""
    rng = np.random.default_rng(seed)
    samples = audio.size
    t = np.arange(samples, dtype=np.float32) / sample_rate

    # Warm low-passed noise. This makes the file sound less like isolated beeps
    # while staying mostly below the frequency band used for the text.
    white = rng.normal(0.0, 1.0, samples).astype(np.float32)
    sos = signal.butter(4, 900, btype="lowpass", fs=sample_rate, output="sos")
    low_noise = signal.sosfilt(sos, white).astype(np.float32)
    low_noise /= max(float(np.max(np.abs(low_noise))), 1e-9)
    audio += noise_gain * low_noise

    # A subtle low drone gives the MP3 an obvious audible body.
    drone = (
        0.55 * np.sin(2 * np.pi * 146.83 * t)
        + 0.35 * np.sin(2 * np.pi * 220.00 * t)
        + 0.25 * np.sin(2 * np.pi * 293.66 * t)
    )
    wobble = 0.65 + 0.35 * np.sin(2 * np.pi * 0.35 * t)
    audio += drone_gain * drone.astype(np.float32) * wobble.astype(np.float32)

    # Light broadband hiss is intentionally small; it makes the spectrogram
    # less sterile without hiding the word.
    hiss = rng.normal(0.0, 1.0, samples).astype(np.float32)
    audio += (noise_gain * 0.12) * hiss


def fade_edges(audio: np.ndarray, sample_rate: int, fade_seconds: float = 0.08) -> None:
    fade_samples = min(int(sample_rate * fade_seconds), audio.size // 2)
    if fade_samples <= 1:
        return
    fade_in = np.linspace(0, 1, fade_samples, dtype=np.float32)
    fade_out = fade_in[::-1]
    audio[:fade_samples] *= fade_in
    audio[-fade_samples:] *= fade_out


def write_mp3(wav_path: Path, mp3_path: Path, bitrate: str) -> None:
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-i",
            str(wav_path),
            "-codec:a",
            "libmp3lame",
            "-b:a",
            bitrate,
            str(mp3_path),
        ],
        check=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate WAV/MP3 audio with a word visible in its spectrogram."
    )
    parser.add_argument("--word", default="amouromeoros")
    parser.add_argument("--duration", type=float, default=8.0)
    parser.add_argument("--sample-rate", type=int, default=44_100)
    parser.add_argument("--min-freq", type=float, default=1_700.0)
    parser.add_argument("--max-freq", type=float, default=11_500.0)
    parser.add_argument("--mask-width", type=int, default=1_000)
    parser.add_argument("--mask-height", type=int, default=240)
    parser.add_argument("--row-step", type=int, default=2)
    parser.add_argument("--tone-gain", type=float, default=0.035)
    parser.add_argument("--noise-gain", type=float, default=0.045)
    parser.add_argument("--drone-gain", type=float, default=0.050)
    parser.add_argument("--seed", type=int, default=13)
    parser.add_argument("--bitrate", default="320k")
    parser.add_argument("--out-dir", type=Path, default=Path("generated_audio"))
    args = parser.parse_args()

    output_dir = args.out_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    safe_word = "".join(ch for ch in args.word.lower() if ch.isalnum()) or "word"
    mask_image = render_word_mask(args.word, args.mask_width, args.mask_height)
    mask_path = output_dir / f"{safe_word}_text_mask.png"
    mask_image.save(mask_path)

    # Darker pixels become active frequencies. Anti-aliased edges are included
    # to keep the rendered spectrogram from looking too blocky.
    mask = np.array(mask_image) < 180

    samples = int(args.sample_rate * args.duration)
    audio = np.zeros(samples, dtype=np.float32)
    add_audible_background(
        audio,
        sample_rate=args.sample_rate,
        seed=args.seed,
        noise_gain=args.noise_gain,
        drone_gain=args.drone_gain,
    )
    add_word_tones(
        audio,
        mask,
        sample_rate=args.sample_rate,
        duration=args.duration,
        min_freq=args.min_freq,
        max_freq=args.max_freq,
        gain=args.tone_gain,
        row_step=args.row_step,
    )
    fade_edges(audio, args.sample_rate)

    peak = max(float(np.max(np.abs(audio))), 1e-9)
    audio = 0.94 * audio / peak

    wav_path = output_dir / f"{safe_word}_spectrogram_word.wav"
    mp3_path = output_dir / f"{safe_word}_spectrogram_word.mp3"
    wavfile.write(wav_path, args.sample_rate, (audio * 32767).astype(np.int16))
    write_mp3(wav_path, mp3_path, args.bitrate)

    print(f"Word: {args.word}")
    print(f"Mask: {mask_path}")
    print(f"WAV: {wav_path}")
    print(f"MP3: {mp3_path}")


if __name__ == "__main__":
    main()
