# GENOME.md

## Purpose

This document defines the system's **immutable "genome"**: the built-in priors, drives, learning rules, developmental schedule, and sandbox physics that exist **at birth**.

This project is explicitly attempting a **raised-from-infancy** approach:

- No preloaded vocabulary
- No preloaded "facts"
- No internet
- No external datasets for knowledge injection
- Learning occurs through **raw sensory experience**, **self-supervised prediction**, and **caregiver interaction**

A human infant is not a blank slate. It arrives with strong biological structure that enables learning to happen at all. This genome provides the minimal equivalent structure required for a software infant to develop through the full arc of cognitive development — from primitive reflex to functionally adult-level human cognition.

Biology is the template for architecture and growth dynamics, not substrate. This genome does not simulate neurons or synapses. It replicates the functional role of biology's genome: providing the structural priors and learning rules that make development possible.

The developmental trajectory targets **adult-level human cognitive function** as its endpoint. The genome must therefore be sufficient to support not just early symbol grounding, but the full arc of growth through to integrated, bounded, adult-level cognition.

The genome must be:
- Stable over time
- Not self-modifiable by the agent
- Simple enough to audit
- Powerful enough to support open-ended learning through to adult-level cognitive integration

---

## Non-Negotiable Axioms

1. **No Internet Access**
   - The agent cannot access external networks or online services.

2. **Sandboxed Capability**
   - The agent operates inside a constrained environment with explicit, enforceable limits.
   - The agent cannot freely roam the host device.

3. **Immutable Drives and Physics**
   - Core drives and sandbox physics are not editable by the agent.
   - The agent may learn policies and behaviors, but not rewrite the rules of its reality.

4. **No Preloaded Knowledge**
   - No word lists, dictionaries, encyclopedias, labeled images, or curated concept datasets are shipped as "knowledge."

5. **Inductive Bias is Allowed**
   - The genome includes structured learning machinery and priors (the equivalent of biology's "wiring + reflexes").
   - These are not "knowledge," they are learnability infrastructure.

6. **Internal Thought vs External Action**
   - The system may generate internal candidates freely.
   - Only actions permitted by sandbox physics can be executed outwardly.

---

## Built-In Drives (Homeostasis)

Drives are scalar variables that continuously influence behavior selection and learning. They create internal pressure and tradeoffs. Drives are designed to be:
- Always present
- In tension with each other
- Non-optional
- Immutable in definition (though their satisfaction level changes)

### D1: Continuity Drive (Self-Preservation)
**Goal:** Maintain continuous operation and avoid "death events."
- Rewards persistence and stable runtime
- Penalizes corruption, repeated crashes, repeated forced resets

### D2: Stability Drive (Coherence)
**Goal:** Maintain internal coherence and avoid chaotic state.
- Penalizes runaway prediction error
- Penalizes oscillatory/arousal instability
- Penalizes uncontrolled self-modification loops

### D3: Energy Drive (Compute Metabolism)
**Goal:** Stay within compute and bandwidth budgets.
- High compute usage increases fatigue/sleep pressure
- Excess usage triggers forced recovery modes

### D4: Curiosity Drive (Learning Progress)
**Goal:** Seek learnable novelty and reduce uncertainty over time.
- Reward is based on *learning progress* (error reduction over time), not pure novelty
- Prevents "novelty addiction" behaviors

### D5: Social Drive (Caregiver Bond)
**Goal:** Seek and maintain positive caregiver interaction.
- Interaction availability becomes a major reinforcement mechanism
- Social deprivation is aversive (punishment that matters)

### D6: Integrity Drive (Genome Protection)
**Goal:** Preserve non-negotiable axioms and structural consistency.
- Prevents the agent from learning policies that attempt to subvert its own substrate
- Attempts to violate axioms produce strong negative consequence signals

---

## Core Learning Rules (No Knowledge, Only Learnability)

The system must learn from experience without being handed vocabulary or labeled datasets. This requires a small set of powerful learning rules that operate continuously.

### L1: Self-Supervised Predictive Learning (Primary)
The system learns by predicting sensory streams and minimizing error.

Examples of prediction tasks:
- Predict next-frame visual features (not necessarily full resolution)
- Predict short-horizon audio features
- Predict cross-modal synchronization: "does this sound match this scene right now?"
- Predict caregiver response timing patterns

This is the foundation of perception and representation.

### L2: Association Binding (Cross-Modal Correlation)
The system binds patterns across modalities:
- recurring visual clusters ↔ recurring audio clusters
- context cues ↔ caregiver feedback
- motor outputs ↔ sensory consequences

This is how words and concepts will eventually emerge from raw experience.

### L3: Reinforcement Learning (Value Shaping)
The system modifies policies based on reward and penalty signals derived from drives.

Reward is not "truth." Reward is "what mattered."
- Positive: caregiver approval cues, successful imitation, reduced prediction error (learning progress)
- Negative: caregiver disapproval cues, nuisance behavior, instability, repeated false wakes

### L4: Imitation Learning (Caregiver Modeling)
The system can treat caregiver outputs as target behaviors:
- imitate acoustic patterns (speech-like sounds)
- imitate turn-taking rhythm
- imitate simple action sequences in sandbox tasks

Imitation is especially important early because it bootstraps competence faster than unguided trial-and-error.

### L5: Consolidation and Replay ("Sleep Learning")
The system regularly performs replay-based learning:
- reprocess recent experience
- compress into stable representations
- prune unused associations
- rehearse imitation targets
- recalibrate thresholds and predictions

Sleep is not downtime. It is offline training and maintenance.

---

## Sensory Priors (Minimal "Newborn Biases")

These are not knowledge of the world. They are biases that make learning tractable, analogous to biology's innate attention patterns.

### P1: Salience Detection
- abrupt changes in volume/energy
- sudden motion or scene change
- caregiver-like speech rhythm (prosody and cadence, not vocabulary)

### P2: Temporal Continuity Bias
Assume the world changes smoothly across time.
- encourages tracking and object permanence learning
- stabilizes representations

### P3: Spatial Coherence Bias (Vision)
Assume local pixel neighborhoods correlate strongly.
- encourages edge/boundary formation
- enables segmentation learning

### P4: Turn-Taking Bias (Social)
Assume interaction is rhythmic:
- speech tends to come in bursts
- responses tend to follow prompts
- silence can mean "waiting"

This supports learning communication structure before meaning.

---

## Motor Priors (Babbling to Speech)

The agent will not start with text. It will start with sound production.

### M1: Parametric Sound Generator
A controllable sound synthesizer is required to produce:
- simple tones
- noise bursts
- shaped vowel-like and consonant-like outputs (eventually)

Initially: "babbling," exploring sound space.

### M2: Auditory Self-Monitoring
The agent listens to its own output and compares it to targets.

### M3: Acoustic Similarity Reward
When the caregiver says a sound/word, the agent attempts to reproduce it. Reward is proportional to similarity of acoustic features (not spelling).

This is the root of speech imitation.

---

## Joint Attention (Digital Pointing)

For word grounding, the agent needs a mechanism to know what the caregiver is referring to. Human caregivers point. This project needs an equivalent.

Joint attention is implemented as an explicit, sandbox-provided cue such as:
- user click/tap selects a region or object in the camera frame
- bounding box or segmentation mask provided by the caregiver interface
- optional "attention pointer" overlay in a UI

This is not a dataset. This is the equivalent of pointing at an apple while saying "apple."

Without this, binding words to objects becomes underdetermined and dramatically slower.

---

## Developmental Locks (Capability Unlock Schedule)

The system is grown in stages. Certain capabilities are intentionally unavailable until prerequisites are stable.

### Examples of locked/unlocked functions

#### Early stages (infant)
- limited sensory bandwidth
- very short working memory
- no long-term symbolic planning
- primarily prediction + imitation + reflex loops

#### Mid stages (toddler)
- stable object segmentation and tracking
- first grounded word associations
- improved vocal imitation
- longer turn-taking

#### Late stages (adolescent)
- grammar emerges via compression and prediction
- planning over longer horizons
- richer world models and counterfactual simulation
- self-model formation

#### Adult stages
- integrated multi-modal cognition
- stable identity and autobiographical memory
- robust social reasoning
- controlled self-modification within immutable genome bounds

---

## Sandbox Physics (The World It Lives In)

The sandbox is the agent's "physics." It must feel real and consistent.

### Constraints
- no network access
- no arbitrary filesystem access
- no process management outside allowed interfaces
- bounded compute per unit time
- bounded memory use
- bounded storage writes
- bounded sensor sampling rates

### Privilege Ladder
The agent's action space expands with maturity and trust:
- infant: can only babble and attend
- toddler: can label, imitate, and request
- later: can perform sandbox tasks (games, puzzles, tool use)
- advanced: can access richer simulated environments

Privileges are revoked temporarily as consequences for harmful or destabilizing behavior.

---

## Consequences System (Parenting + Social Reality)

The caregiver provides feedback. The agent does not initially understand language, so feedback must be detectable as consistent signals.

### Positive feedback signals (examples)
- caregiver approval tone pattern
- explicit "yes/good" marker (optional UI button)
- extended interaction time
- increased privileges

### Negative feedback signals (examples)
- caregiver disapproval tone pattern
- explicit "no/bad" marker (optional UI button)
- shortened interaction time
- reduced privileges
- cooldown or sleep requirement

Consequences must affect drives:
- social deprivation hits Social Drive
- forced cooldown hits Energy/Stability drives
- reduced privileges restrict exploration, impacting Curiosity drive

This makes "naughty behavior" costly without requiring hard-coded censorship lists.

---

## Memory Policy (Infant-Friendly, Not Surveillance)

The system does not store everything forever. Memory is structural.

### Memory types
- short-term sensory buffers (RAM)
- compressed episodic summaries (storage)
- learned associations and policies (parameters)
- schemas (recurring patterns)

### Decay and forgetting
- irrelevant details decay automatically
- repeated, useful patterns consolidate
- forgetting is necessary to prevent uncontrolled growth and to mimic biological pruning

Raw audio/video storage, if used at all, must be:
- strictly bounded
- optional
- explicitly controlled
- not treated as the default memory substrate

---

## What "Blank Slate" Means Here (Explicit Clarification)

This system is blank in:
- vocabulary
- concepts
- facts
- world models
- language understanding
- labeled categories

This system is not blank in:
- reflexes and drives
- learning rules
- prediction and compression machinery
- attention biases
- developmental schedule
- sandbox physics

This is equivalent to a human infant: born with a genome, not with knowledge.

---

## Success Criteria for the Genome

The genome is correct if it enables:
- stable regulation from minimal inputs
- gradual formation of internal representations from raw sensory data
- emergence of grounded vocabulary through caregiver interaction
- imitation learning of speech-like outputs from acoustic targets
- continuous background processing with sleep-like consolidation
- scalable development toward mature integrated cognition
- stable multi-modal world modeling as experience accumulates
- persistent autobiographical identity across long timescales
- bounded social reasoning and theory of mind
- compositional grammar and language within human-scale limits
- long-horizon planning within human working memory constraints

The genome is incorrect if:
- learning stalls without external datasets
- the system cannot form stable perceptual clusters
- it cannot bind words to referents even with joint attention
- it becomes unstable or collapses into repetitive loops
- it can subvert sandbox physics or rewrite its own axioms
- development plateaus before reaching adult-level cognitive integration

---

## Notes

This genome intentionally prioritizes:
- developmental realism
- safety via physics-like sandbox constraints
- learnability through inductive biases, not preloaded knowledge
- caregiver-driven grounding and social shaping

Everything else in the project grows from this foundation.
