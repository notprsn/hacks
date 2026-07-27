#!/usr/bin/env python3
"""Render spectrogram images from an audio file."""

from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", str(Path(".matplotlib-cache").resolve()))

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
from scipy import signal


def decode_audio(path: Path, sample_rate: int) -> np.ndarray:
    cmd = [
        "ffmpeg",
        "-v",
        "error",
        "-i",
        str(path),
        "-f",
        "f32le",
        "-acodec",
        "pcm_f32le",
        "-ac",
        "1",
        "-ar",
        str(sample_rate),
        "-",
    ]
    result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE)
    audio = np.frombuffer(result.stdout, dtype=np.float32)
    if audio.size == 0:
        raise ValueError(f"No samples decoded from {path}")
    return audio


def compute_spectrogram(
    audio: np.ndarray,
    sample_rate: int,
    n_fft: int,
    hop: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    frequencies, times, stft = signal.stft(
        audio,
        fs=sample_rate,
        window="hann",
        nperseg=n_fft,
        noverlap=n_fft - hop,
        boundary=None,
        padded=False,
    )
    db = 20 * np.log10(np.maximum(np.abs(stft), 1e-10))
    return frequencies, times, db


def plot_spectrogram(
    frequencies: np.ndarray,
    times: np.ndarray,
    db: np.ndarray,
    output: Path,
    *,
    title: str,
    min_freq: float | None = None,
    max_freq: float | None = None,
    cmap: str = "gray_r",
    percentile_clip: tuple[float, float] = (8.0, 99.8),
    show_axes: bool = True,
) -> None:
    keep = np.ones_like(frequencies, dtype=bool)
    if min_freq is not None:
        keep &= frequencies >= min_freq
    if max_freq is not None:
        keep &= frequencies <= max_freq
    frequencies = frequencies[keep]
    db = db[keep, :]

    vmin, vmax = np.percentile(db, percentile_clip)
    if vmin >= vmax:
        vmin = float(np.min(db))
        vmax = float(np.max(db))

    figsize = (18, 8) if show_axes else (18, 5)
    fig, ax = plt.subplots(figsize=figsize, dpi=180)
    mesh = ax.pcolormesh(
        times,
        frequencies / 1000.0,
        db,
        shading="auto",
        cmap=cmap,
        vmin=vmin,
        vmax=vmax,
    )

    if show_axes:
        ax.set_title(title)
        ax.set_xlabel("Time (seconds)")
        ax.set_ylabel("Frequency (kHz)")
        fig.colorbar(mesh, ax=ax, label="Amplitude (dB)")
        fig.tight_layout()
    else:
        ax.set_axis_off()
        fig.subplots_adjust(left=0, right=1, bottom=0, top=1)

    fig.savefig(output)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description="Render spectrogram PNGs.")
    parser.add_argument(
        "audio",
        type=Path,
        nargs="?",
        default=Path("generated_audio/amouromeoros_spectrogram_word.mp3"),
    )
    parser.add_argument("--sample-rate", type=int, default=44_100)
    parser.add_argument("--n-fft", type=int, default=4096)
    parser.add_argument("--hop", type=int, default=256)
    parser.add_argument("--out-dir", type=Path, default=Path("spectrogram_renders"))
    args = parser.parse_args()

    audio_path = args.audio.resolve()
    output_dir = args.out_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    audio = decode_audio(audio_path, args.sample_rate)
    frequencies, times, db = compute_spectrogram(
        audio,
        sample_rate=args.sample_rate,
        n_fft=args.n_fft,
        hop=args.hop,
    )

    stem = audio_path.stem
    plot_spectrogram(
        frequencies,
        times,
        db,
        output_dir / f"{stem}_full.png",
        title=f"{audio_path.name} spectrogram, full range",
        min_freq=0,
        max_freq=14_000,
        cmap="magma",
        percentile_clip=(3.0, 99.8),
    )
    plot_spectrogram(
        frequencies,
        times,
        db,
        output_dir / f"{stem}_word_band.png",
        title=f"{audio_path.name} spectrogram, word band",
        min_freq=1_300,
        max_freq=12_200,
        cmap="gray_r",
        percentile_clip=(8.0, 99.85),
    )
    plot_spectrogram(
        frequencies,
        times,
        db,
        output_dir / f"{stem}_word_band_clean.png",
        title=f"{audio_path.name} spectrogram, word band",
        min_freq=1_300,
        max_freq=12_200,
        cmap="gray_r",
        percentile_clip=(8.0, 99.85),
        show_axes=False,
    )

    print(f"Input: {audio_path}")
    print(f"Output directory: {output_dir}")
    for image in sorted(output_dir.glob(f"{stem}_*.png")):
        print(image)


if __name__ == "__main__":
    main()
