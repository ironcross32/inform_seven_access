"""Attenuate PCM cues while retaining NVDA's normal WaveFileCommand playback."""

from __future__ import annotations

from os import PathLike


import atexit
import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
import wave


_cacheDirectory: TemporaryDirectory[str] | None = None


def scaledSoundPath(source: str | PathLike[str], volume: int) -> Path:
    """Return an immutable cached WAV; never modify source files or system volume.

    WaveFileCommand has no per-command gain. Scaling these short cues before
    queuing them keeps NVDA's existing timing, audio routing and cancellation.
    Keep generated files until exit so queued commands survive plugin reloads.
    """
    global _cacheDirectory
    source = Path(source)
    if volume == 100:
        return source
    if not 0 < volume < 100:
        raise ValueError("Sound volume must be between 1 and 100")
    if _cacheDirectory is None:
        _cacheDirectory = TemporaryDirectory(prefix="inform7-sounds-")
        _ = atexit.register(_cacheDirectory.cleanup)
    stat = source.stat()
    key = f"{source.resolve()}:{stat.st_mtime_ns}:{stat.st_size}:{volume}"
    path = Path(_cacheDirectory.name) / (hashlib.sha256(key.encode("utf-8")).hexdigest() + ".wav")
    if path.is_file():
        return path
    with wave.open(str(source), "rb") as original:
        params = original.getparams()
        width = original.getsampwidth()
        if original.getcomptype() != "NONE" or width not in (1, 2, 3, 4):
            raise ValueError("Unsupported syntax sound format")
        data = original.readframes(original.getnframes())
    result = bytearray(len(data))
    for offset in range(0, len(data), width):
        # 8-bit WAV PCM is unsigned with silence at 128; other PCM is signed.
        sample = int.from_bytes(
            data[offset : offset + width],
            "little",
            signed=width != 1,
        )
        if width == 1:
            sample -= 128
        sample = round(sample * volume / 100)
        if width == 1:
            sample += 128
        result[offset : offset + width] = sample.to_bytes(width, "little", signed=width != 1)
    with wave.open(str(path), "wb") as output:
        output.setparams(params)
        output.writeframes(result)
    return path
