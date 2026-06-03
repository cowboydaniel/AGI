FROM python:3.12-slim

# No network access at runtime — enforced by --network=none at docker run time
# Build-time only: install deps
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

WORKDIR /app
COPY src/ ./src/

# Persistent state lives here — mount a volume to survive restarts
RUN mkdir -p /app/data

# Sandbox flags (pass at docker run):
#   --cap-drop=ALL --read-only --network=none --tmpfs /tmp -v acd_data:/app/data
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/src

CMD ["python", "src/main.py"]
