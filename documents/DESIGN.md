# DESIGN.md

This document defines the architectural principles governing the ACD system. For project context, see [README.md](README.md). For motivation and scientific rationale, see [MISSION.md](MISSION.md).

---

## System Boundary

The system is not a robot. It is not embodied in mechanical hardware. It exists as a computational process with access to:

- Microphone (auditory input)
- Camera (visual input)
- Speaker (auditory output)
- Persistent storage (long-term memory)
- Compute resources (processing substrate)

All external interaction occurs through these interfaces. The system has no other channels to the outside world.

---

## Core Design Principles

### 1. Continuous Processing

The system must never be logically idle. Even in low-activity states, it performs background maintenance, prediction, and calibration.

Different operational regimes exist (e.g., sleep, wake, focused), but all involve active internal processing.

---

### 2. Developmental Growth

The architecture is not built as a fully formed adult system. It is grown in stages:

- Regulatory primitives first
- Reflexive control next
- Gating and inhibition
- Prediction
- Memory formation
- Value systems
- Higher cognition

Each stage must be stable before adding complexity.

---

### 3. Modular but Integrated

The system will consist of semi-specialized modules analogous to:

- Arousal regulation (brainstem-like)
- Sensory gating
- Prediction engine
- Value/reward system
- Memory consolidation
- Executive control
- Specialized skill modules (vision, speech, planning)

Modules are distinct but communicate via shared internal representations.

---

### 4. Metabolic Budgeting

Compute usage is regulated by a global internal "metabolic" model.

Operational intensity varies depending on:

- Arousal level
- Environmental novelty
- Interaction frequency
- Internal predictive error
- System stability

This prevents uncontrolled compute escalation and mimics biological energy constraints.

---

### 5. Prediction as Core Mechanism

The fundamental computational principle is prediction and error minimization.

The system continuously:

1. Generates internal predictions.
2. Compares predictions to sensory input or replayed memory.
3. Updates internal parameters to reduce error.

Operational modes differ primarily in how strongly external sensory input influences prediction.

---

### 6. Memory as Structural Change

Memory is not a database of raw recordings.

Memory consists of:

- Compressed representations
- Pattern extraction
- Behavioral adjustments
- Structural parameter updates
- Reinforcement of useful pathways
- Decay and pruning of irrelevant information

Forgetting is intentional and required.

---

### 7. Sleep and Consolidation

Sleep states are not inactivity.

Sleep modes perform:

- Log compression
- Model calibration
- Replay-based learning
- Threshold tuning
- Self-diagnostics
- Structural pruning

External sensory weighting is reduced but internal simulation remains active.

---

### 8. Value and Reinforcement

The system must develop an internal scalar value signal that:

- Reinforces successful outcomes
- Penalizes nuisance behaviors
- Strengthens useful predictive structures
- Shapes behavioral policy

Value signals are necessary for meaningful adaptation.

---

### 9. Stability Before Intelligence

Higher-level reasoning modules (language understanding, planning, abstract reasoning) must not be introduced before:

- Stable arousal regulation exists
- Inhibitory control exists
- Prediction loop is functional
- Memory consolidation is reliable
- Value system is operational

The root of intelligence is regulation, not knowledge.

---

### 10. Developmental Maturity Target

A developmentally mature ACD system will demonstrate the functional properties of an adult human mind:

- Continuous predictive modeling
- Adaptive behavior across contexts
- Persistent autobiographical identity
- Long-term memory integration
- Self-calibration
- Value-driven decision making
- Robust multi-modal perception
- Controlled self-modification within genome bounds
- Stable social reasoning and theory of mind
- Compositional language and grammar within human-scale limits
- Long-horizon planning within human working memory constraints

This is the explicit developmental target: functionally adult-level human cognition implemented in software.

---

### 11. Bounded Cognitive Scope

The target is human-like capability with human-like limits.

This system is not designed to become a superintelligent optimizer. It is designed to approximate the cognitive structure and behavior of an adult human mind:

- Working memory bounded to human-scale context windows
- Processing speed constrained by metabolic budgeting
- Knowledge built from embodied experience, not encyclopedic ingestion
- Reasoning bounded by the same bottlenecks that constrain human thought

The goal is cognitive fidelity to the human developmental endpoint, not cognitive maximization beyond it.

---

## Open Questions

The following are deliberately unresolved at this stage of the project. They are recorded here to acknowledge them as real gaps, not to dismiss them.

### Genome Sufficiency

The current genome (see [GENOME.md](GENOME.md)) specifies 6 drives, 5 learning rules, 4 sensory priors, and 3 motor priors. Whether this minimal set is sufficient to support development through to adult-level cognitive integration is the project's central empirical question. The genome is a starting hypothesis. It may require expansion based on results from early developmental stages. See GENOME.md's "Genome Versioning" section for the revision policy.

### Implementation Technology

The architectural principles in this document are deliberately substrate-agnostic. Implementation will require concrete choices about:

- Neural network architectures (or alternatives) for the prediction engine and association binding
- Programming language and runtime environment
- Compute infrastructure and real-time scheduling
- Audio/video processing pipelines
- Storage and state management for persistent memory

These choices are deferred until the architectural design is stable, but they are not trivial. The "right" substrate for a developmental system may differ significantly from conventional deep learning infrastructure. This is acknowledged as an open engineering problem.

### Developmental Timescales

Human cognitive development takes approximately 20 years of continuous sensory input from a rich environment. The relationship between biological developmental time and computational developmental time is unknown. The project does not assume real-time equivalence, but also does not assume arbitrary speedup is possible — some developmental processes may have inherent sequential dependencies that resist parallelization.
