FROM python:3.12-slim

# No network access at runtime — enforced by --network=none at docker run time.
# Build-time only: install system libraries and Python dependencies.

# System libraries required by some Python packages:
#   libgl1, libglib2.0-0  → opencv-python (cv2)
#   libportaudio2         → sounddevice (PortAudio bindings)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libgl1 \
        libglib2.0-0 \
        libportaudio2 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python dependencies. Installed from requirements.txt so the dependency set
# has a single source of truth (mirrored in pyproject.toml). torch/torchvision/
# torchaudio resolve to CPU wheels via the extra index declared in that file.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/

# Persistent state lives here — mount a volume to survive restarts
RUN mkdir -p /app/data

# Sandbox flags (pass at docker run):
#   --cap-drop=ALL --read-only --network=none --tmpfs /tmp -v acd_data:/app/data
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/src

CMD ["python", "src/main.py"]
