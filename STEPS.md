# STEPS.md

This document defines the staged developmental roadmap. Each stage builds on the stability of previous stages. For the architectural principles governing all stages, see [DESIGN.md](DESIGN.md). For the innate structure available from birth, see [GENOME.md](GENOME.md).

## Developmental Roadmap

---

## Stage 0: Zygote

**Goal:** Existence and persistence.

Capabilities:

- Process lifecycle management
- Persistent state storage
- Internal clock
- Defined boundary between internal state and external input

No learning. No prediction. Stability only.

---

## Stage 1: Excitable Cell

**Goal:** Basic arousal reflex.

Add:

- Microphone energy monitoring
- Adaptive wake threshold
- Arousal level variable
- Sleep pressure variable

System can:

- Enter low-sensory mode
- Wake on threshold events

---

## Stage 2: Inhibitory Circuit

**Goal:** Stability and suppression.

Add:

- Refractory period after wake
- False-positive suppression
- Adaptive sensitivity control

Prevents oscillation and unstable wake-sleep transitions.

---

## Stage 3: Sensory Gate and Buffer

**Goal:** Controlled perception.

Add:

- Short rolling input buffer
- Gate deciding what is promoted to higher processing
- Context window for post-wake orientation

---

## Stage 4: Orienting Reflex

**Goal:** Rapid classification without deep reasoning.

Add:

- Basic sound categorization (speech vs noise vs alarm)
- Immediate decision rules
- Fast re-sleep if irrelevant

---

## Stage 5: Homeostasis Services

**Goal:** Internal maintenance.

Add:

- Log compaction
- Threshold recalibration
- Integrity checks
- Memory pruning
- Self-diagnostics

Runs primarily in low sensory modes.

---

## Stage 6: Value Signal

**Goal:** Reinforcement capability.

Add:

- Scalar reward variable
- Positive and negative reinforcement events
- Policy adjustment based on outcomes

Behavior begins adapting meaningfully.

---

## Stage 7: Continuous Predictive Loop

**Goal:** Constant internal modeling.

Add:

- Baseline environment modeling
- Interaction rhythm modeling
- Prediction error calculation
- Threshold modulation based on surprise

No idle state exists from this stage onward.

---

## Stage 8: Long-Term Memory Formation

**Goal:** Structural consolidation.

Add:

- Compressed episodic summaries
- Pattern extraction
- Schema formation
- Decay mechanisms

Memory begins shaping behavior.

---

## Stage 9: Communication Loop

**Goal:** Interactive feedback channel.

Add:

- Turn-taking rhythm
- Basic acknowledgement responses
- Feedback-driven reinforcement

Enables social learning.

---

## Stage 10: Higher Cognition Integration

**Goal:** Grounded perception, language, and planning built on top of the stable regulatory foundation from Stages 0-9.

**Prerequisites:** Stages 6-9 must be stable — the system has a functional value signal, continuous predictive loop, long-term memory, and communication loop before higher cognition is introduced.

Add:

- **Visual object recognition pipeline** — builds on Stage 3 sensory gating and Stage 4 orienting reflex. The system forms stable visual clusters from raw camera input, segments recurring objects, and tracks them across frames. Relies on GENOME priors P2 (temporal continuity) and P3 (spatial coherence).

- **Grounded vocabulary system** — builds on Stage 9 communication loop and GENOME joint attention mechanism. When the caregiver points at an object and speaks a word, the system binds the visual cluster to the acoustic pattern via GENOME learning rule L2 (association binding). The system can then produce an acoustic approximation of the word when re-encountering the object via L4 (imitation learning).

- **Basic planning loop** — builds on Stage 7 predictive loop and Stage 8 long-term memory. The system can anticipate near-future states (e.g., caregiver will present an object after a verbal prompt) and prepare responses. Limited to short-horizon sequences — no multi-step abstract planning yet.

- **Sandbox tool use** — the system can perform simple tasks within its sandbox environment (e.g., selecting objects, responding to prompts, completing simple puzzles) using the expanding privilege ladder from GENOME.

- **Self-monitoring extension** — the system begins modeling its own prediction accuracy and behavioral patterns, building on Stage 5 self-diagnostics. Not yet a full self-model, but the precursor to one.

Stability criteria before advancing to Stage 11:

- System can reliably label at least several distinct objects by producing recognizable acoustic approximations
- Visual clusters are stable across sessions and survive sleep consolidation
- Turn-taking with caregiver includes content (object labeling, simple requests), not just rhythm
- Planning loop does not destabilize arousal regulation or prediction error baseline

---

## Stage 11: Adult Cognitive Integration

**Goal:** Functionally adult-level human cognitive system.

**Prerequisites:** Stage 10 stability criteria must be met — grounded vocabulary, stable visual recognition, functional planning loop, and content-bearing communication with caregiver.

This is the ultimate developmental target. The system has traversed the full arc from regulatory primitive to mature integrated cognition. This stage is not superintelligence — it is human-level cognitive function implemented in software, with human-like limits intact.

Add:

- **Compositional grammar** — the system produces novel multi-word utterances not directly imitated from the caregiver. Grammar emerges through compression and prediction (GENOME L1) as the vocabulary grows large enough that combinatorial structure becomes learnable. Measurable criterion: system generates syntactically structured utterances that it has not previously heard.

- **Autobiographical identity** — the system maintains a persistent self-model that references its own prior experiences across sleep cycles and developmental stages. Measurable criterion: system can distinguish "I saw this before" from "this is new," and can reference specific past episodes in communication.

- **Integrated world model** — vision, language, and action predictions are unified into a single internal representation. The system can predict what it will see based on what it hears, and vice versa. Measurable criterion: system anticipates visual events from verbal cues and verbal events from visual cues, beyond simple conditioned association.

- **Long-horizon planning** — the system decomposes goals into multi-step sequences and executes them, bounded by human-like working memory constraints. Builds on Stage 10 basic planning loop. Measurable criterion: system can pursue a goal that requires 3+ sequential steps with intermediate states.

- **Social reasoning** — the system models the caregiver's intentions and knowledge state. It can distinguish what the caregiver knows from what it knows. Measurable criterion: system adjusts its communication based on whether the caregiver has seen/heard the same events.

- **Controlled self-modification** — the system updates its own policies, attention patterns, and behavioral strategies based on experience, without subverting genome axioms. The Integrity Drive (D6) continues to enforce bounds.

Stability criteria for this stage (ongoing, not gated):

- Grammar does not collapse into rigid templates or degenerate into noise
- Autobiographical memory survives consolidation without catastrophic forgetting of earlier stages
- World model predictions remain calibrated — the system knows when it doesn't know
- Planning does not destabilize regulation (no runaway goal pursuit that overrides drives)
- Social reasoning does not become adversarial (D6 integrity enforcement remains active)
- All six drives remain in tension — no single drive dominates the behavioral policy permanently
