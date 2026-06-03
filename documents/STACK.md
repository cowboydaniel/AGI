# STACK.md

This document defines the technology stack for the first implementation of the ACD system. For architectural principles, see [DESIGN.md](DESIGN.md). For project context, see [README.md](README.md).

---

## Recommended Prototype Stack

Use **Python + PyTorch** for the first implementation.

**Reasons:**
- Python is fastest for research iteration.
- PyTorch has strong GPU acceleration, deep learning tooling, `torchvision`, and `torchaudio`. Current PyTorch stable supports Python 3.10+ and CUDA builds.
- JAX is powerful, but better suited later if large-scale compiled numerical pipelines are needed.

---

## Runtime

| Role | Choice |
|---|---|
| Primary | Python 3.11 or 3.12 |
| Later (performance-critical sensor/runtime components only) | Rust or C++ |

---

## ML Framework

| Role | Choice |
|---|---|
| Primary | PyTorch |
| Packages | `torch`, `torchvision`, `torchaudio` |

---

## Predictive Engine

Start simple. Do not start with large transformers — they are too data-hungry and too adult-brain-like for the infant stage.

**Vision:** small CNN encoder + recurrent/SSM-style temporal predictor
**Audio:** 1D convolution encoder over waveform or spectrogram + recurrent/SSM predictor
**Shared latent:** contrastive/predictive cross-modal bridge

**Suggested progression:**

1. CNN / Conv1D encoders
2. GRU or small state-space model for temporal continuity
3. Contrastive predictive coding for cross-modal synchrony
4. Small transformer — only after stable latent representations exist

---

## Reinforcement / Sandbox Environments

Use **Gymnasium-style environment interfaces** for sandbox tasks. Gymnasium is the maintained successor to OpenAI Gym and provides a standard observation/action/reward loop compatible with most RL libraries.

---

## Audio Input / Output

| Role | Choice |
|---|---|
| Raw microphone recording and speaker playback | `sounddevice` |
| Waveform buffers | `numpy` |
| Spectrograms, transforms, ML preprocessing | `torchaudio` |

`sounddevice` provides PortAudio bindings and can play/record NumPy arrays across Linux, macOS, and Windows.

---

## Parametric Sound Generator

Start with a **custom Python generator** using:
- sine waves
- noise
- amplitude envelopes
- frequency sweeps
- formant-like filters (later)

Do not begin with text-to-speech. The infant must learn sound production, not use adult speech synthesis.

---

## Storage

| Role | Choice |
|---|---|
| Structured runtime state | SQLite |
| Logs and checkpoints | flat files |
| Learned parameters | PyTorch checkpoints (`.pt`) |

---

## First-Stack Summary

```
Language:           Python 3.11 / 3.12
ML:                 PyTorch
Vision:             OpenCV + torchvision + PyTorch
Audio:              sounddevice + torchaudio + NumPy
RL interface:       Gymnasium-style custom environments
Storage:            SQLite + file checkpoints
UI/caregiver:       simple local web UI or PySide/Qt (later)
```

**Core rule:** prototype in Python/PyTorch first. Optimize later, only after the learning loop proves itself.
