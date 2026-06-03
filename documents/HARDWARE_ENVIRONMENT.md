# HARDWARE_ENVIRONMENT.md

This document defines the hardware and software environment requirements for the ACD system. For the technology stack, see [STACK.md](STACK.md). For sandbox enforcement, see [SANDBOX.md](SANDBOX.md).

---

## 1. Purpose

The system must support:
- real-time audio capture
- real-time or near-real-time camera input
- self-supervised predictive learning
- replay/consolidation during sleep states
- containerized sandbox execution
- bounded resource usage

The first prototype must prioritize stability over scale.

---

## 2. Hardware Tiers

### 2.1 Tier 0: Minimal Development Machine

Use only for: event bus development, sandbox testing, caregiver UI, simple audio tests, non-real-time model experiments.

```
CPU:       4 cores / 8 threads
RAM:       16 GB
GPU:       optional
VRAM:      none required
Storage:   50 GB free
Camera:    USB webcam or laptop camera
Mic:       USB or built-in
Speaker:   any output device
OS:        Linux preferred
```

Expected limitations: no serious visual learning, slow model training, reduced frame rate, limited replay/consolidation.

### 2.2 Tier 1: Prototype Learning Machine

Use for: low-resolution visual prediction, object tracking, audio imitation, early cross-modal learning.

```
CPU:       8 cores / 16 threads
RAM:       32 GB
GPU:       NVIDIA GPU recommended
VRAM:      8 GB minimum
Storage:   250 GB free SSD
Camera:    USB webcam capable of 720p (used initially at low resolution)
Mic:       decent USB microphone
Speaker:   controllable output device
OS:        Linux
```

Initial operating settings:

```
video:      160×120 to 224×224, 5–15 FPS
audio:      16 kHz mono, 20–50 ms chunks
```

### 2.3 Tier 2: Recommended Research Machine

Use for: continuous experiments, visual/audio latent learning, replay/consolidation, cross-modal association, longer developmental runs.

```
CPU:       12+ cores
RAM:       64 GB
GPU:       NVIDIA RTX-class
VRAM:      12–16 GB minimum
Storage:   1 TB SSD
Camera:    USB camera with manual exposure/focus control preferred
Mic:       low-noise USB microphone
Speaker:   low-latency speaker/headphones
OS:        Linux
```

This is the preferred target for serious early ACD work.

### 2.4 Tier 3: Extended Development Machine

Use for: larger latent models, longer replay windows, larger vector memory, multi-camera experiments, richer sandbox environments.

```
CPU:       16+ cores
RAM:       128 GB
GPU:       16–24 GB+ VRAM
Storage:   2 TB+ NVMe SSD
Optional:  second GPU for training/consolidation
OS:        Linux
```

---

## 3. Current Machine Suitability

A machine with:

```
CPU:  Intel Core i9-14900K
GPU:  RTX 4070 Ti Super
RAM:  64 GB DDR5
```

is suitable for **Tier 2 prototype and early research development**.

Expected capability:
- low-resolution visual prediction
- audio imitation learning
- cross-modal experiments
- sleep/replay batch training
- caregiver UI
- containerized sandbox testing

The main limitation will likely be model design and data stability, not raw compute.

---

## 4. GPU Requirements

### 4.1 Is a GPU Required?

```
Stage 0–1:         no GPU required
Stage 2+:          GPU strongly recommended
Visual learning:   GPU effectively required for practical iteration
```

### 4.2 Minimum VRAM

```
4 GB:    possible only for tiny experiments
8 GB:    minimum practical prototype
12–16 GB: recommended
24 GB+:  useful for larger models and longer replay
```

### 4.3 GPU Use Policy

**Use GPU for:**
```
visual encoder
audio encoder
latent prediction model
replay/consolidation batches
cross-modal training
```

**Use CPU for:**
```
event bus
sensory gating
audio energy detection
basic motion detection
sandbox enforcement
logging
caregiver UI
```

Do not send every raw input directly into heavy GPU processing.

---

## 5. Audio Pipeline Requirements

### 5.1 Initial Settings

```
sample_rate:   16 kHz
channels:      mono
chunk_size:    20–50 ms
format:        float32
```

16 kHz mono is low enough for efficient processing, sufficient for early tone and speech-like imitation, and manageable for real-time feedback.

### 5.2 Audio Latency Targets

```
audio energy / arousal latency:    < 100 ms
audio imitation feedback latency:  < 200 ms
speaker stop / mute latency:       < 250 ms
```

### 5.3 Audio Hardware

**Minimum:** built-in mic and speaker.

**Recommended:** USB microphone, wired speaker/headphones, low-noise recording environment.

**Avoid early use of Bluetooth audio** — latency, compression, and inconsistent feedback timing make it unsuitable for the imitation learning loop.

---

## 6. Video Pipeline Requirements

### 6.1 Initial Settings

```
resolution:  160×120 or 224×224
FPS:         5–15
color:       RGB
format:      uint8 input, float32 tensor after preprocessing
```

Do not start with HD video. HD increases compute load before the system has learned stable perception.

### 6.2 Video Latency Targets

```
frame capture latency:          < 100 ms
visual encoding latency:        < 200 ms
object tracking update:         < 200 ms
caregiver pointer update:       < 200 ms
```

### 6.3 Camera Recommendations

**Minimum:** standard USB webcam.

**Recommended:** USB webcam with manual exposure/focus, stable mount, consistent lighting, plain background for early tests.

**Avoid early experiments with:** moving handheld cameras, complex cluttered backgrounds, rapid lighting changes.

The infant stage needs controlled sensory conditions.

---

## 7. Storage Requirements

### 7.1 Minimum

```
50 GB free
```

Enough for logs, small checkpoints, and early experiments.

### 7.2 Recommended

```
250 GB to 1 TB SSD
```

Model checkpoints grow quickly, replay buffers need space, experiments require versioned results, and metrics/logging accumulate over time.

### 7.3 Storage Rules

Raw audio/video:
```
disabled by default
bounded if enabled
deleted or compressed aggressively
```

Persistent storage should prioritize:
```
latents
episodic summaries
metrics
checkpoints
association graphs
```

---

## 8. Operating System Requirements

### 8.1 Preferred OS

```
Linux — Ubuntu 24.04 LTS or compatible modern distro
```

Linux is preferred for better container support, GPU container support, device isolation, and long-running service management.

### 8.2 Windows

Not recommended as the first host environment. Acceptable only with WSL2 + NVIDIA GPU support, but camera/microphone passthrough may complicate the architecture.

### 8.3 macOS

Possible for CPU/MPS experiments, but not recommended for the main project. The GPU stack, container constraints, and CUDA/PyTorch workflow alignment differ from Linux.

---

## 9. Containerization Requirements

### 9.1 Required

The agent runtime must run inside a container or equivalent sandbox. Recommended: Docker or Podman.

Docker supports CPU and memory constraints for containers; by default containers can use as much host CPU/memory as the kernel scheduler allows, so explicit limits are required.

### 9.2 GPU Containers

For NVIDIA GPU access inside containers, use the **NVIDIA Container Toolkit**. It configures Docker to use the NVIDIA container runtime.

### 9.3 Container Restrictions

```
no internet
no privileged mode
no host filesystem access except explicit mounts
no Docker socket
no SSH keys
no host PID namespace
no unnecessary Linux capabilities
read-only root filesystem where possible
```

---

## 10. Recommended Runtime Split

Do not give the agent container direct hardware access where avoidable.

```
Host Sensor Services
  - camera capture
  - microphone capture
  - speaker output

Capability Broker
  - filters and approves access
  - rate limits
  - logs actions

Agent Container
  - receives approved streams
  - emits approved action requests
```

This allows the host to control devices while the agent remains sandboxed.

---

## 11. Python / ML Environment

```
Python:       3.11 or 3.12
ML:           PyTorch (requires Python 3.10+)
Vision:       torchvision, opencv-python
Audio:        torchaudio, sounddevice
Numerics:     numpy
Storage:      SQLite
Vector index: FAISS (optional)
```

---

## 12. Real-Time Constraints

### 12.1 Soft Real-Time

The system does not need medical/device-grade hard real-time timing. It needs soft real-time responsiveness:
- occasional dropped frames are acceptable
- delayed background learning is acceptable
- audio safety controls must remain responsive

### 12.2 Must Never Block on Training

```
audio arousal monitoring
speaker mute / stop
sandbox violation handling
shutdown / pause controls
event bus critical path
```

---

## 13. Thermal and Long-Run Stability

Long-running experiments require adequate cooling, stable power, and active monitoring.

Recommended monitoring:
```
nvidia-smi
docker stats
systemd service watchdogs
application heartbeat logs
```

---

## 14. First Environment Milestone

```
Run the ACD runtime inside a container with:
  - no network
  - CPU/RAM limits enforced
  - writable sandbox directory only
  - working event bus
  - working caregiver UI
  - audio input through broker
  - camera input through broker
  - speaker output through broker
  - audit logs active
```

No machine learning success is required for this milestone. This is purely environment validation.

---

## 15. Final Recommendation

```
Host OS:       Linux
Container:     Docker or Podman
GPU:           NVIDIA with Container Toolkit
ML stack:      Python + PyTorch
Camera:        low-resolution stream (160×120 to 224×224)
Audio:         16 kHz mono
Resource limits: explicit CPU/RAM caps on container
Sensor access: host-controlled broker, not direct device passthrough
```

Do not scale model size until object tracking and audio imitation are stable at low resolution.
