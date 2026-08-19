# CLAUDE.md

## Project

This is the **Artificial Cognitive Development (ACD)** project. The goal is to build a sandboxed digital cognitive system that develops from infant-level perception toward adult-level cognition entirely through staged developmental growth — no pretraining, no labeled datasets, no injected knowledge.

The long-term objective is a functionally adult human-level cognitive architecture grown through developmental stages, using human neurodevelopment as the template for architecture and growth dynamics, not substrate.

This project is **not** a chatbot, language model, or autonomous agent. It does not start with language, vocabulary, object labels, or human knowledge. It starts with raw perception, drives, and the capacity to learn.

See [README.md](README.md) for the project overview.

---

## Repository Structure

```
README.md               Project overview
CLAUDE.md               This file
pyproject.toml          Package metadata (packages `acd*` only; src/ is unpackaged)
requirements.txt        Install source used by the Dockerfile (adds the torch CPU index)
Dockerfile              python:3.12-slim; copies src/, runs `python src/main.py`
docker-compose.yml
documents/              All design and specification documents
  MISSION.md            MEMORY_ARCHITECTURE.md
  DESIGN.md             HARDWARE_ENVIRONMENT.md
  GENOME.md             EVALUATION_PROTOCOL.md
  STEPS.md              STAGE_CRITERIA.md
  STACK.md              CAREGIVER_INTERFACE.md
  MODULES.md            PREDICTIVE_ENGINE.md
  DATA_FLOW.md          SANDBOX.md
src/                    THE LIVE RUNTIME — flat modules, imported by PYTHONPATH
acd/                    Staged target package layout — scaffolding only, all files empty
sandbox/                Runtime mount points (checkpoints/, state/, tmp/) — .gitkeep only
tests/                  unit/, integration/, evaluation/
tools/                  mic_diag.py — microphone diagnostic
scripts/                checkpoint.sh, run_container.sh, run_dev.sh — all empty stubs
```

### Two source trees — read this before writing code

- **`src/` is the live system.** Flat modules, no package, imported via `PYTHONPATH=/app/src`.
  This is what `src/main.py` boots and what the Dockerfile ships.
- **`acd/` is the target layout** described in MODULES.md (`acd/bus/`, `acd/modules/`,
  `acd/models/`, `acd/memory/`, `acd/sensors/`, `acd/sandbox/`, `acd/state/`, `acd/genome/`,
  `acd/ui/`). Every one of its ~51 `.py` files is currently **empty**. It is a
  directory-shaped plan, not code.

Do not add behaviour to `acd/` unless you are deliberately performing the migration.
Continue Stage work in `src/` and match the conventions already there.

---

## Implementation Status

Stages 0–7 of [documents/STEPS.md](documents/STEPS.md) are implemented in `src/`
(~2,400 lines). Each module carries a docstring naming its stage.

| Stage | Name | Module |
|-------|------|--------|
| 0 | Zygote | `src/main.py`, `src/state_store.py` (SQLite), `src/clock.py`, `src/sandbox.py` |
| 1 | Excitable Cell | `src/bus.py`, `src/events.py` (typed async pub/sub) |
| 2 | Inhibitory Circuit | `src/arousal.py` (refractory periods, oscillation damping) |
| 3 | Sensory Gate and Buffer | `src/sensory_gate.py` (hardware probing, arousal-linked throttling) |
| 4 | Orienting Reflex | `src/orienting.py` (heuristic sound categorisation, no ML) |
| 5 | Homeostasis Services | `src/homeostasis.py` (four sleep-time maintenance services) |
| 6 | Value Signal | `src/value.py` (reinforcement / value), `src/mic_input.py` (live mic capture) |
| 7 | Continuous Predictive Loop | `src/predictor.py` (online linear latent predictor + rhythm model) |

Stage 8 (long-term memory), Stage 9 (communication loop), and Stages 10–11 are unbuilt.

**Reality checks on the stack:**
- The only sensory modality wired up is **audio**. There is no camera path yet —
  `src/` has no vision module, so success criteria A, C, and D are not yet reachable.
- **PyTorch is declared but unused.** Nothing in `src/` imports torch; only `numpy` and
  `sounddevice` are actually imported. The Stage 7 predictor is hand-rolled SGD on a
  single linear layer — deliberately the simplest JEPA-shaped thing that learns.
- FAISS, OpenCV, and gymnasium are declared dependencies with no call sites yet.
- The `scripts/*.sh` helpers are empty files.

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

## What To Do When Asked To Implement

Work continues from **Stage 8** of [documents/STEPS.md](documents/STEPS.md) unless told
otherwise. Before starting any stage:

1. Read that stage's section in STEPS.md and its exit conditions in
   [documents/STAGE_CRITERIA.md](documents/STAGE_CRITERIA.md).
2. Check [documents/MODULES.md](documents/MODULES.md) (section: Initialization Order) —
   `src/main.py` boots modules in that order and annotates each with its slot number.
3. Add the module to `src/`, wire its `init()` into `main.py` at the correct position,
   and add tests under `tests/unit/` plus an integration test named for the stage
   (the existing pattern is `tests/integration/test_stage6_value.py`).

Do not skip ahead, and do not begin a stage whose predecessor has not met its criteria.

---

## Core Design Philosophy

The system **develops** rather than being populated. Knowledge is not inserted — it emerges.

Five principles govern all design decisions, in priority order:

1. **Prediction** — self-supervised predictive learning is the primary mechanism
2. **Development** — capabilities must be staged; later capabilities grow from earlier ones
3. **Grounding** — symbols must bind to perception, not to tokens or lookup tables
4. **Continuity** — the system persists and learns across time
5. **Containment** — the sandbox is mandatory and inviolable

Every implementation decision should be evaluated against these principles.

---

## Architectural Priorities

Do not skip levels. Do not build advanced cognition before foundational systems are stable.

```
1.  Stable runtime
2.  Sandbox integrity
3.  Arousal regulation
4.  Sensory processing
5.  Predictive learning
6.  Object persistence
7.  Audio imitation
8.  Cross-modal integration
9.  Grounded symbol formation
10. Higher cognition
```

---

## First Success Criteria

The project succeeds when any of the following are achieved:

**A — Object persistence:** a visual object is tracked from raw camera input across time without labels. The system does not need to know what it is — only that it persists.

**B — Sound imitation:** the system hears a sound and learns to manipulate the speaker to approximate it. No language understanding required.

**C — Cross-modal binding:** the system forms a repeatable association between a visual object and a caregiver-produced sound pattern.

**D — Grounded symbol:** the system produces a learned sound when an associated object appears, or attends to the associated object when the sound is heard — without caregiver pointing during the test.

---

## Implementation Rules

### Anti-Hardcoding Rule

**This is the most important rule in the project.**

When evaluating any implementation, ask:

> *Does this provide the mechanism for learning, or does it secretly provide the answer?*

**Mechanisms are allowed. Answers are not.**

Do not hardcode:
- object labels, vocabulary, grammar, concepts, or world knowledge
- object recognition, speech recognition, or symbol mappings
- visual categories, language rules, or reasoning rules
- behavioral policies that bypass learning
- solutions to developmental milestones

The system may be given a genome, developmental drives, learning mechanisms, predictive architectures, memory systems, sandbox constraints, and sensory/motor interfaces. These are equivalent to biological instincts and neural structure. The architecture may be innate. Knowledge must not be.

If a capability is intended to emerge through learning, it must not be manually implemented.

### Language Rule

Language is a late developmental capability, not the starting point.

The system must first learn:
```
Perception → Persistence → Prediction → Association → Attention
```

Only then should language-like behavior emerge. Avoid text-first solutions. Avoid token-centric designs. Grounding comes first.

### Cross-Modal Rule

Vision and audio must not be connected through manually defined symbolic mappings. Cross-modal integration must emerge from shared events, temporal synchrony, prediction, attention, and reinforcement.

### Memory Rule

Memory is compressed predictive structure, not archival storage. The system should remember useful experiences, stable associations, and reinforced patterns. It should forget noise, unused associations, and unstable structures. Forgetting is required.

### Sandbox Rule

The sandbox is the world. The system may learn within it; it may not rewrite it. All external interaction must pass through the capability broker. The agent must never receive internet access, host OS access, arbitrary filesystem access, direct hardware control, or the ability to modify its genome or sandbox policy.

### Caregiver Rule

The caregiver structures experience — providing attention guidance, feedback, repetition, and social reinforcement. The caregiver does not provide datasets, labels, object detection, or hidden shortcuts. The system learns from experience, not from injected knowledge.

### Evaluation Rule

No milestone is complete because of a single impressive result. All milestones must be measured, logged, reproducible, stable across sessions, and evaluated against negative controls. If it cannot be measured, it does not count.

---

## Preferred Technical Direction

```
Language:          Python 3.11/3.12
ML framework:      PyTorch
Architecture:      event-driven async (asyncio)
Sandbox:           containerized (Docker/Podman)
Predictive model:  JEPA-style latent prediction
Memory:            graph-based associative + FAISS vector + SQLite metadata
Consolidation:     replay-based sleep learning
```

Better approaches may be adopted if they remain consistent with the project philosophy.

---

## Implementation Guidance

**Prefer:** simplicity, interpretability, stability, developmental realism.

**Avoid:** unnecessary complexity, massive models, premature scaling, hidden pretrained knowledge.

Start small. Prove fundamentals. Expand only after stability is achieved.

---

## Document Conventions

- All specification documents live in `documents/`
- Cross-links between documents use relative paths (e.g., `[MODULES.md](MODULES.md)` from within `documents/`)
- Every document opens with a short cross-reference block linking to related docs
- No implementation code lives in document files

---

## Final Principle

The purpose of this project is not to simulate intelligence.

The purpose is to investigate whether cognition can emerge through developmental learning from raw sensory experience inside a strictly controlled digital environment.
