"""Creates the tiny placeholder files the workflows need so ComfyUI accepts them
before the member uploads their own (silent voice clip, blank frame)."""
import os
import struct
import sys
import wave
import zlib

out = sys.argv[1]
os.makedirs(out, exist_ok=True)

# 1 second of silence, used when the voice switch is off
with wave.open(os.path.join(out, "aiempire_no_voice.wav"), "wb") as w:
    w.setnchannels(1)
    w.setsampwidth(2)
    w.setframerate(16000)
    w.writeframes(b"\0\0" * 16000)

# 64x64 grey PNG, used when the start/end switch is off
def png(path, size=64, grey=128):
    raw = b"".join(b"\0" + bytes([grey, grey, grey]) * size for _ in range(size))
    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0))
                + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))

png(os.path.join(out, "aiempire_blank.png"))
print("assets ok:", sorted(os.listdir(out)))
