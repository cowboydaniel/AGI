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
