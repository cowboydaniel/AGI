# CLAUDE.md

## Project

This is the **Artificial Cognitive Development (ACD)** project. The goal is to build a sandboxed digital cognitive system that develops from infant-level perception toward adult-level cognition entirely through staged developmental growth — no pretraining, no labeled datasets, no injected knowledge.

See [README.md](README.md) for the project overview.

---

## Repository Structure

```
README.md               Project overview
CLAUDE.md               This file
documents/              All design and specification documents
  MISSION.md
  DESIGN.md
  GENOME.md
  STEPS.md
  STACK.md
  MODULES.md
  DATA_FLOW.md
  PREDICTIVE_ENGINE.md
  CAREGIVER_INTERFACE.md
  SANDBOX.md
  STAGE_CRITERIA.md
  MEMORY_ARCHITECTURE.md
  HARDWARE_ENVIRONMENT.md
  EVALUATION_PROTOCOL.md
```

There is no source code yet. The current phase is documentation and architecture design.

---

## Key Design Decisions

- **Language:** Python 3.11/3.12
- **ML framework:** PyTorch
- **Predictive engine:** JEPA-style latent prediction — not diffusion, not pixel-reconstruction MAE, not a large transformer at the infant stage
- **Communication:** async event bus (Python `asyncio`), typed messages, pub/sub
- **Sandbox:** Docker/Podman container, no network, capability broker mediates all sensor/actuator access
- **Memory:** hybrid — neural weights + episodic summaries + associative graph + FAISS vector store + SQLite metadata
- **Audio:** `sounddevice` + `torchaudio`, 16 kHz mono, 20–50 ms chunks
- **Storage:** SQLite for state/metadata, PyTorch checkpoints for model weights, FAISS for vector index

---

## Development Branch

Active development branch: `claude/keen-curie-KfL33`

---

## What To Do When Asked To Implement

The project has no code yet. When asked to begin implementation, start from Stage 0 of [documents/STEPS.md](documents/STEPS.md) and build upward. The initialization order is defined in [documents/MODULES.md](documents/MODULES.md) (section: Initialization Order).

Stage 0 requires only:
- process lifecycle management
- persistent state storage
- internal clock
- defined sandbox boundary

No ML, no sensors, no learning. Stability only.

---

## Document Conventions

- All specification documents live in `documents/`
- Cross-links between documents use relative paths (e.g., `[MODULES.md](MODULES.md)` from within `documents/`)
- Every document opens with a short cross-reference block linking to related docs
- No implementation code lives in document files
