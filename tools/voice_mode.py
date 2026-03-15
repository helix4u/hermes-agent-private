#!/usr/bin/env python3
"""
Optional CLI voice mode helpers.

This module is intentionally scoped for local CLI use:
- push-to-talk recording with sounddevice/numpy when available
- transcription via the existing tools.transcription_tools module
- best-effort local audio playback for TTS output

It does not attempt to provide the full upstream Discord voice-channel stack.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import threading
import time
import wave
from pathlib import Path
from typing import Dict, Optional

from tools.transcription_tools import transcribe_audio, is_stt_enabled

try:
    import numpy as np
except Exception:  # pragma: no cover - optional dependency
    np = None

try:
    import sounddevice as sd
except Exception:  # pragma: no cover - optional dependency
    sd = None


DEFAULT_SAMPLE_RATE = 16000
DEFAULT_CHANNELS = 1


def get_voice_cache_dir() -> Path:
    """Return the Hermes voice cache directory."""
    voice_dir = Path.home() / ".hermes" / "voice_cache"
    voice_dir.mkdir(parents=True, exist_ok=True)
    return voice_dir


def cleanup_stale_voice_files(max_age_hours: int = 24) -> None:
    """Delete old cached recordings so the cache stays bounded."""
    cutoff = time.time() - (max_age_hours * 3600)
    for path in get_voice_cache_dir().glob("voice_*.wav"):
        try:
            if path.stat().st_mtime < cutoff:
                path.unlink(missing_ok=True)
        except Exception:
            continue


def detect_audio_environment() -> Dict[str, object]:
    """Return a simple snapshot of local audio capability."""
    env = {
        "recording_available": bool(sd and np and _has_input_device()),
        "playback_available": _can_play_audio(),
        "stt_enabled": is_stt_enabled(),
        "cache_dir": str(get_voice_cache_dir()),
    }
    return env


def _can_play_audio() -> bool:
    if shutil.which("ffplay"):
        return True
    if os.name == "nt":
        return True
    return bool(
        shutil.which("afplay")
        or shutil.which("paplay")
        or shutil.which("aplay")
        or shutil.which("mpg123")
    )


def _has_input_device() -> bool:
    if sd is None:
        return False
    try:
        for device in sd.query_devices():
            if int(device.get("max_input_channels", 0) or 0) > 0:
                return True
    except Exception:
        return False
    return False


def check_voice_requirements() -> Dict[str, object]:
    """Return availability and any missing dependencies for CLI voice mode."""
    missing = []
    if sd is None or np is None:
        missing.append("Install optional voice deps: pip install sounddevice numpy")
    elif not _has_input_device():
        missing.append("No usable audio input device was detected for voice recording")
    if not is_stt_enabled():
        missing.append("Speech-to-text is disabled in ~/.hermes/config.yaml (stt.enabled: false)")
    if not (os.getenv("VOICE_TOOLS_OPENAI_KEY") or os.getenv("OPENAI_API_KEY")):
        missing.append("Set VOICE_TOOLS_OPENAI_KEY or OPENAI_API_KEY for transcription")
    return {
        "ok": not missing,
        "missing": missing,
        "environment": detect_audio_environment(),
    }


def play_beep(frequency: int = 880, duration_ms: int = 120) -> None:
    """Emit a short local beep when possible."""
    try:
        if os.name == "nt":
            import winsound

            winsound.Beep(frequency, duration_ms)
        else:
            print("\a", end="", flush=True)
    except Exception:
        pass


class AudioRecorder:
    """Simple push-to-talk recorder backed by sounddevice."""

    def __init__(
        self,
        sample_rate: int = DEFAULT_SAMPLE_RATE,
        channels: int = DEFAULT_CHANNELS,
        max_duration: int = 120,
    ) -> None:
        if sd is None or np is None:
            raise RuntimeError("Voice recording dependencies are not installed.")
        self.sample_rate = sample_rate
        self.channels = channels
        self.max_duration = max_duration
        self._lock = threading.Lock()
        self._stream = None
        self._frames = []
        self._recording = False
        self._start_time = 0.0

    @property
    def is_recording(self) -> bool:
        with self._lock:
            return self._recording

    def start(self) -> None:
        """Start recording from the default input device."""
        with self._lock:
            self._frames = []
            self._recording = True
            self._start_time = time.time()

        def callback(indata, frames, time_info, status) -> None:
            del frames, time_info, status
            with self._lock:
                if not self._recording:
                    return
                self._frames.append(indata.copy())
                if (time.time() - self._start_time) >= self.max_duration:
                    self._recording = False

        self._stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype="int16",
            callback=callback,
        )
        self._stream.start()

    def stop(self) -> Optional[str]:
        """Stop recording and write a UTF-8-safe cached WAV file."""
        with self._lock:
            self._recording = False
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            finally:
                self._stream = None

        if not self._frames:
            return None

        audio_data = np.concatenate(self._frames, axis=0)
        cleanup_stale_voice_files()
        fd, path = tempfile.mkstemp(
            prefix="voice_",
            suffix=".wav",
            dir=str(get_voice_cache_dir()),
        )
        os.close(fd)

        with wave.open(path, "wb") as wav_file:
            wav_file.setnchannels(self.channels)
            wav_file.setsampwidth(2)
            wav_file.setframerate(self.sample_rate)
            wav_file.writeframes(audio_data.tobytes())

        return path


def transcribe_recording(file_path: str) -> Dict[str, object]:
    """Transcribe a local recording through the existing STT tool."""
    return transcribe_audio(file_path)


def play_audio_file(file_path: str) -> bool:
    """Best-effort local playback for a generated audio file."""
    path = str(Path(file_path).expanduser())
    if not os.path.exists(path):
        return False

    try:
        if shutil.which("ffplay"):
            subprocess.run(
                ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", path],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True

        if os.name == "nt":
            suffix = Path(path).suffix.lower()
            if suffix == ".wav":
                import winsound

                winsound.PlaySound(path, winsound.SND_FILENAME)
                return True
            ps_path = path.replace("'", "''")
            subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-STA",
                    "-Command",
                    (
                        "Add-Type -AssemblyName presentationCore; "
                        f"$player = New-Object System.Windows.Media.MediaPlayer; "
                        f"$player.Open([Uri]'{ps_path}'); "
                        "$deadline = [DateTime]::UtcNow.AddSeconds(60); "
                        "while ($player.NaturalDuration.HasTimeSpan -eq $false -and [DateTime]::UtcNow -lt $deadline) { Start-Sleep -Milliseconds 100 }; "
                        "$player.Play(); "
                        "while ($player.Position -lt $player.NaturalDuration.TimeSpan -and [DateTime]::UtcNow -lt $deadline) { Start-Sleep -Milliseconds 200 }; "
                        "$player.Stop(); "
                        "$player.Close();"
                    ),
                ],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True

        for player in ("afplay", "paplay", "aplay", "mpg123"):
            if shutil.which(player):
                subprocess.run(
                    [player, path],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                return True
    except Exception:
        return False

    return False
