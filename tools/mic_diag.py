"""
Standalone mic diagnostic. Run with: python3 tools/mic_diag.py
Prints all audio devices, then records 2 seconds from each input device
and reports the RMS so you can identify which one is live.
"""

import sys
import time

try:
    import numpy as np
    import sounddevice as sd
except ImportError as e:
    print(f"Missing dependency: {e}")
    sys.exit(1)

print("=== Audio devices ===")
devices = sd.query_devices()
for i, d in enumerate(devices):
    marker = " <-- default" if i == sd.default.device[0] else ""
    if d["max_input_channels"] > 0:
        print(f"  [{i}] IN  {d['name']!r}  ch={d['max_input_channels']}  rate={d['default_samplerate']:.0f}{marker}")
    else:
        print(f"  [{i}] OUT {d['name']!r}")

print(f"\nDefault input device index: {sd.default.device[0]}")
print(f"Default output device index: {sd.default.device[1]}")

print("\n=== Recording 2s from each input device ===")
for i, d in enumerate(devices):
    if d["max_input_channels"] == 0:
        continue
    try:
        sr = int(d["default_samplerate"])
        frames = sd.rec(int(sr * 2), samplerate=sr, channels=1,
                        dtype="float32", device=i, blocking=True)
        rms = float(np.sqrt(np.mean(frames ** 2)))
        peak = float(np.max(np.abs(frames)))
        print(f"  [{i}] {d['name']!r}  rms={rms:.4f}  peak={peak:.4f}  {'<-- HAS SIGNAL' if rms > 0.001 else 'silent/zero'}")
    except Exception as e:
        print(f"  [{i}] {d['name']!r}  ERROR: {e}")

print("\n=== Quick live test (default device, 1s) ===")
print("Make noise now...")
frames = sd.rec(16000, samplerate=16000, channels=1, dtype="float32", blocking=True)
rms = float(np.sqrt(np.mean(frames ** 2)))
print(f"  rms={rms:.4f}  {'WORKING' if rms > 0.001 else 'SILENT — wrong device or permission issue'}")
