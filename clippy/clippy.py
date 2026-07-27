#!/usr/bin/env python3
"""
Clippy — the local helper for cutting exact song clips.

The pretty UI lives on notprsn.github.io/projects/clippy/ (and is also served straight
from this helper at http://localhost:8765). But the heavy lifting — grabbing
the song off YouTube and cutting the exact slice you selected — happens right
here on your laptop. Nothing leaves your machine, nothing is public.

Run start-clippy.command, start-clippy.bat, or start-clippy.sh once. The launcher
creates a private environment and installs the two Python dependencies.
"""

import glob
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import imageio_ffmpeg
import yt_dlp

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(HERE, ".clippy_cache")
PORT = int(os.environ.get("CLIPPY_PORT", "8765"))
HOSTED_URL = "https://notprsn.github.io/projects/clippy/"
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
AUDIO_EXTS = ("m4a", "webm", "opus", "mp3", "ogg", "mp4", "aac", "flac", "wav")
MAX_CLIP_SECONDS = 600  # sanity cap

os.makedirs(CACHE_DIR, exist_ok=True)


class ClipError(Exception):
    """Something the user should see, not a crash."""


# --------------------------------------------------------------------------
# lyrics (proxy lrclib so the browser never hits a CORS wall)
# --------------------------------------------------------------------------
def search_lyrics(query):
    url = "https://lrclib.net/api/search?" + urllib.parse.urlencode({"q": query})
    req = urllib.request.Request(url, headers={"User-Agent": "clippy (local helper)"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    out = []
    for r in data:
        if not r.get("syncedLyrics"):
            continue  # no timestamps => can't map "selected text" to a time range
        out.append(
            {
                "id": r.get("id"),
                "trackName": r.get("trackName"),
                "artistName": r.get("artistName"),
                "albumName": r.get("albumName"),
                "duration": r.get("duration"),
                "syncedLyrics": r.get("syncedLyrics"),
            }
        )
    return out


# --------------------------------------------------------------------------
# audio: find on YouTube (best duration match), download once, cache
# --------------------------------------------------------------------------
def _cached_file(video_id):
    for ext in AUDIO_EXTS:
        hits = glob.glob(os.path.join(CACHE_DIR, f"{video_id}.{ext}"))
        if hits:
            return hits[0]
    return None


def resolve_audio(url=None, query=None, target_duration=None, log=print):
    """Return (local_audio_path, meta) for the best source, downloading if needed."""
    common = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        # the default web client frequently gets HTTP 403 on the audio stream;
        # the android client downloads reliably.
        "extractor_args": {"youtube": {"player_client": ["android", "web"]}},
        "ffmpeg_location": FFMPEG,
    }

    if url:
        with yt_dlp.YoutubeDL({**common, "skip_download": True}) as ydl:
            meta = ydl.extract_info(url, download=False)
        video_id = meta["id"]
        video_url = meta.get("webpage_url", url)
        title = meta.get("title")
    else:
        if not query:
            raise ClipError("Need a song to search for.")
        log(f"[clippy] searching YouTube: {query}")
        with yt_dlp.YoutubeDL({**common, "extract_flat": True, "skip_download": True}) as ydl:
            info = ydl.extract_info(f"ytsearch6:{query}", download=False)
        entries = [e for e in (info.get("entries") or []) if e and e.get("id")]
        if not entries:
            raise ClipError("No YouTube match found for that song.")
        if target_duration:
            # pick the result whose length best matches the lyrics' track length,
            # so the timestamps we selected actually line up with the audio
            entries.sort(
                key=lambda e: abs((e.get("duration") or 0) - target_duration)
                if e.get("duration")
                else 9e9
            )
        best = entries[0]
        video_id = best["id"]
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        title = best.get("title")

    cached = _cached_file(video_id)
    if cached:
        log(f"[clippy] cache hit: {os.path.basename(cached)}")
        return cached, {"id": video_id, "title": title, "url": video_url}

    log(f"[clippy] downloading audio: {title or video_url}")
    outtmpl = os.path.join(CACHE_DIR, f"{video_id}.%(ext)s")
    with yt_dlp.YoutubeDL(
        {**common, "format": "bestaudio/best", "outtmpl": outtmpl}
    ) as ydl:
        ydl.download([video_url])

    path = _cached_file(video_id)
    if not path:
        raise ClipError("Downloaded the audio but couldn't find the file.")
    return path, {"id": video_id, "title": title, "url": video_url}


# --------------------------------------------------------------------------
# cut: ffmpeg, exact slice -> mp3
# --------------------------------------------------------------------------
def cut_to_mp3(src, start, end, fade=True):
    duration = end - start
    if duration <= 0:
        raise ClipError("The end of the clip is before the start.")
    if duration > MAX_CLIP_SECONDS:
        raise ClipError(f"That clip is too long ({int(duration)}s). Keep it under {MAX_CLIP_SECONDS}s.")

    fd, out_path = tempfile.mkstemp(suffix=".mp3")
    os.close(fd)

    cmd = [
        FFMPEG, "-y",
        "-ss", f"{start:.3f}",
        "-i", src,
        "-t", f"{duration:.3f}",
        "-vn", "-ac", "2",
        "-c:a", "libmp3lame", "-q:a", "2",
    ]
    if fade and duration > 0.3:
        af = f"afade=t=in:st=0:d=0.05,afade=t=out:st={duration - 0.05:.3f}:d=0.05"
        cmd += ["-af", af]
    cmd += [out_path]

    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0 or not os.path.getsize(out_path):
        raise ClipError("ffmpeg couldn't cut the clip:\n" + proc.stderr[-500:])
    return out_path


def _safe(s, fallback=""):
    s = re.sub(r'[\\/:*?"<>|]+', " ", str(s or fallback)).strip()
    return re.sub(r"\s+", " ", s) or fallback


def _stamp(sec):
    sec = max(0, int(round(sec)))
    return f"{sec // 60}m{sec % 60:02d}s"


# --------------------------------------------------------------------------
# http
# --------------------------------------------------------------------------
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # quieter default logging
        pass

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _json(self, code, obj):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self._cors()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/health":
            return self._json(200, {"ok": True, "service": "clippy", "version": yt_dlp.version.__version__})

        if path == "/lyrics":
            qs = urllib.parse.parse_qs(parsed.query)
            q = (qs.get("q") or [""])[0].strip()
            if not q:
                return self._json(400, {"error": "Give me something to search for."})
            try:
                return self._json(200, {"results": search_lyrics(q)})
            except Exception as e:  # noqa: BLE001
                return self._json(502, {"error": f"Lyrics lookup failed: {e}"})

        return self._serve_static(path)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != "/clip":
            return self._json(404, {"error": "not found"})
        try:
            length = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(length) or b"{}")
        except Exception:  # noqa: BLE001
            return self._json(400, {"error": "Bad request body."})

        try:
            title = (payload.get("title") or "").strip()
            artist = (payload.get("artist") or "").strip()
            url = (payload.get("url") or "").strip() or None
            start = float(payload.get("start"))
            end = float(payload.get("end"))
            target = payload.get("duration")
            target = float(target) if target else None
            fade = bool(payload.get("fade", True))
        except (TypeError, ValueError):
            return self._json(400, {"error": "start/end must be numbers."})

        query = " ".join(p for p in (title, artist) if p) or url
        if not query:
            return self._json(400, {"error": "Need a song (title/artist) or a YouTube URL."})

        try:
            src, meta = resolve_audio(url=url, query=query, target_duration=target, log=lambda m: print(m, flush=True))
            out = cut_to_mp3(src, start, end, fade=fade)
        except ClipError as e:
            return self._json(422, {"error": str(e)})
        except Exception as e:  # noqa: BLE001
            return self._json(500, {"error": f"Unexpected error: {e}"})

        fname = f"{_safe(artist)} - {_safe(title, meta.get('title') or 'clip')} [{_stamp(start)}-{_stamp(end)}].mp3".strip(" -")
        try:
            with open(out, "rb") as f:
                data = f.read()
            self.send_response(200)
            self._cors()
            self.send_header("Content-Type", "audio/mpeg")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Content-Disposition", f'attachment; filename="{fname}"')
            self.send_header("X-Clippy-Filename", fname)
            self.end_headers()
            self.wfile.write(data)
        finally:
            try:
                os.remove(out)
            except OSError:
                pass

    def _serve_static(self, path):
        rel = path.lstrip("/") or "index.html"
        full = os.path.normpath(os.path.join(HERE, rel))
        if not full.startswith(HERE) or not os.path.isfile(full):
            return self._json(404, {"error": "not found"})
        ctype = {
            ".html": "text/html; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".js": "text/javascript; charset=utf-8",
            ".svg": "image/svg+xml",
            ".png": "image/png",
            ".ico": "image/x-icon",
        }.get(os.path.splitext(full)[1], "application/octet-stream")
        with open(full, "rb") as f:
            body = f.read()
        self.send_response(200)
        self._cors()
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main():
    if subprocess.run([FFMPEG, "-version"], capture_output=True).returncode != 0:
        sys.exit("Clippy's private ffmpeg could not start. Run the launcher again.")

    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print("📎  Clippy helper is up.")
    print(f"    Website:      {HOSTED_URL}")
    print(f"    Local UI:     http://localhost:{PORT}")
    print(f"    Cache:        {CACHE_DIR}")
    print("    Ctrl+C to stop.\n")
    if os.environ.get("CLIPPY_NO_BROWSER") != "1":
        webbrowser.open(HOSTED_URL)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n📎  bye!")
        server.shutdown()


if __name__ == "__main__":
    main()
