# MEMORY_ARCHITECTURE.md

This document specifies the memory and storage architecture for the ACD system. For the module that executes consolidation and replay, see [MODULES.md](MODULES.md) (Module 11). For data flow context, see [DATA_FLOW.md](DATA_FLOW.md). For storage technology choices, see [STACK.md](STACK.md).

---

## 1. Purpose

The ACD system requires persistent memory across developmental time.

Memory is not treated as:
- raw video archive
- full sensory replay
- static database storage

Memory is treated as:

```
compressed experience useful for future prediction
```

The system remembers:
- patterns
- associations
- recurring structures
- reinforced interactions
- useful predictions
- stable object identities

The system forgets:
- noise
- unstable patterns
- unused associations
- low-value transient events

---

## 2. Memory Philosophy

The memory system is intentionally hybrid. No single storage format is sufficient. The architecture uses:

```
1. Neural weights
2. Episodic summaries
3. Associative graph memory
4. Vector similarity memory
5. Working memory buffers
6. Procedural motor memory
```

Each serves a different purpose.

---

## 3. Memory Layers

### 3.1 Working Memory

**Purpose:** active short-term context, current attention, current predictions, recent sensory windows.

**Lifetime:** milliseconds → minutes

**Storage:** RAM only — ring buffers, temporary tensors. Not persisted long-term.

### 3.2 Episodic Memory

**Purpose:** compressed summaries of important experiences; replay during sleep/consolidation; developmental continuity.

**Examples:**
```
object tracking episode
audio imitation attempt
joint attention interaction
cross-modal binding event
```

**Lifetime:** minutes → years. Persisted to disk.

### 3.3 Associative Memory

**Purpose:** relationship storage — object ↔ sound binding, event ↔ reward linkage, attention ↔ outcome linkage.

**Structure:** graph-based memory.

Nodes:
```
objects
audio patterns
events
attention targets
episodes
```

Edges:
```
association strength
temporal relation
causal confidence
reinforcement history
```

Persisted to disk.

### 3.4 Vector Similarity Memory

**Purpose:** latent lookup, nearest-neighbor matching, recognition support, replay candidate selection.

**Stores:**
```
latent embeddings
compressed object signatures
audio signatures
cross-modal signatures
```

**Prototype:** FAISS or lightweight vector store.

### 3.5 Procedural Memory

**Purpose:** learned motor mappings, speaker control, stable behavioral policies.

Stored primarily in model weights, policy weights, and motor control parameters.

### 3.6 Developmental Memory

**Purpose:** long-term developmental continuity, stage progression, milestone history, reward history, stability trends.

Stored as structured metadata.

---

## 4. On-Disk Storage Layout

```
/sandbox/state/
    runtime_state.db
    development_state.json

/sandbox/checkpoints/
    visual_encoder/
    audio_encoder/
    predictor/
    motor_policy/
    replay_snapshots/

/sandbox/memory/
    episodic/
    associative_graph/
    vector_store/

/sandbox/logs/
    events/
    metrics/
    audit/
```

---

## 5. Episodic Memory Format

### 5.1 Philosophy

An episodic memory is not a raw video or audio recording. It is compressed structured experience. The system remembers the important latent structure of the episode.

### 5.2 Episodic Record Structure

```json
{
  "episode_id": "uuid",
  "timestamp_start": 12345.1,
  "timestamp_end": 12355.8,
  "episode_type": "OBJECT_ATTENTION",

  "attention_target_id": "object_003",

  "visual_summary_latent": [ ... ],
  "audio_summary_latent": [ ... ],
  "cross_modal_summary_latent": [ ... ],

  "prediction_error_mean": 0.21,
  "prediction_error_delta": -0.08,

  "reward_total": 0.74,
  "feedback_events": [
    "GOOD",
    "GOOD",
    "NO"
  ],

  "object_tracking_confidence": 0.82,

  "association_candidates": [
    {
      "audio_pattern_id": "audio_017",
      "binding_strength": 0.61
    }
  ],

  "importance_score": 0.77,
  "decay_score": 0.12
}
```

---

## 6. Why Episodic Compression Exists

Raw storage is dangerous because storage explodes, replay becomes impossible, noise dominates, and irrelevant detail accumulates.

Instead, replay should focus on useful structure and summaries should preserve prediction-relevant information. Memory should resemble semantic compression, not surveillance recording.

---

## 7. Associative Graph Memory

### 7.1 Structure

```
Node:
  id
  type
  latent_signature
  creation_time
  stability_score

Edge:
  source
  target
  edge_type
  strength
  confidence
  reinforcement_history
  decay_score
```

### 7.2 Example Graph

```
object_003
   ↔ audio_017
   ↔ episode_120
   ↔ caregiver_positive_feedback
```

This allows association strengthening, multi-hop recall, replay selection, and contextual retrieval.

---

## 8. Vector Memory

### 8.1 Purpose

Supports nearest-neighbor retrieval, object re-identification, audio similarity, and replay clustering.

### 8.2 Stored Data

Each vector entry includes:

```
embedding
timestamp
association references
stability score
usage frequency
```

Example types stored:
```
visual object latent
audio latent
cross-modal latent
attention latent
episode latent
```

---

## 9. Neural Weights as Memory

The majority of long-term procedural learning exists implicitly in model weights:
- visual feature extraction
- audio structure
- prediction dynamics
- motor control
- temporal continuity

---

## 10. Forgetting and Decay

### 10.1 Philosophy

Forgetting is required. Without forgetting, memory becomes noise, storage explodes, weak associations pollute learning, and false bindings persist forever.

The system should remember: **stable + useful + reinforced patterns.**

### 10.2 Decay Score

Each memory element has:

```
decay_score ∈ [0, 1]

0 = stable/preserved
1 = immediate deletion candidate
```

### 10.3 Decay Inputs

```
time_since_last_use
reinforcement_history
prediction_utility
association_strength
replay_frequency
caregiver_feedback
stability_score
```

### 10.4 Example Decay Function

```
decay_score =
    sigmoid(
      age_weight    * time_since_last_access
    - reward_weight * cumulative_reward
    - replay_weight * replay_count
    - utility_weight * prediction_improvement
    )
```

### 10.5 Deletion Rules

Delete if:
```
decay_score > threshold
AND association_strength low
AND unused for configured duration
```

Never immediately delete:
- high-reward memories
- stable object identities
- core developmental milestones

---

## 11. Replay System

### 11.1 Purpose

Replay simulates sleep consolidation. The system revisits important episodes, unstable predictions, reinforced associations, and recent learning events.

### 11.2 Replay Selection

Priority **increases** with:
```
importance_score
prediction_error
recent_reward
association_growth
novelty
```

Priority **decreases** with:
```
high decay
low utility
stale unused content
```

### 11.3 Replay Output

```
updated model weights
stronger associations
pruned weak associations
compressed summaries
```

---

## 12. Memory Consolidation Pipeline

```
Raw sensory events
  → latent encoding
  → working memory
  → episode segmentation
  → episodic compression
  → associative extraction
  → replay selection
  → consolidation
  → long-term storage
```

---

## 13. Episode Segmentation

The system must decide where one episode ends and another begins.

Segmentation triggers:
```
major attention shift
caregiver episode start/end
large prediction error jump
sleep transition
strong reinforcement event
object disappearance
```

---

## 14. Importance Scoring

Every episode receives:

```
importance_score ∈ [0, 1]
```

Factors:
```
prediction error
reward magnitude
novelty
association growth
caregiver interaction density
replay usefulness
```

High-importance episodes replay more often, decay slower, and compress less aggressively.

---

## 15. Checkpointing

### 15.1 Purpose

The system must support rollback, recovery, regression testing, and developmental auditing.

### 15.2 Checkpoint Types

**Lightweight Checkpoint** (frequency: minutes)
```
runtime state
small memory summary
recent latent state
```

**Developmental Checkpoint** (frequency: hours or milestone completion)
```
all model weights
association graph snapshot
memory metadata
development stage
metrics
```

---

## 16. Storage Technology Recommendations

| Role | Technology |
|---|---|
| Structured metadata (episodes, metrics, state, audit logs) | SQLite |
| Graph memory (prototype) | NetworkX in-memory, serialized to disk |
| Graph memory (later) | graph database if needed |
| Vector similarity memory | FAISS |
| Neural weights | PyTorch checkpoints |

---

## 17. Compression Philosophy

Compression should preserve **predictive utility**, not pixel-perfect reconstruction.

The system remembers what mattered, what predicted outcomes, what became stable — not every detail.

---

## 18. First Memory Milestones

**Milestone 1:**
```
The system can store an object-tracking episode, replay it later,
improve prediction stability after replay, and strengthen the object
identity association.
```

**Milestone 2:**
```
The system stores repeated audio imitation attempts and improves after replay.
```

**Milestone 3:**
```
The system stores cross-modal object/sound associations that survive across sessions.
```

---

## 19. Final Rule

```
Memory is not archival storage.
Memory is compressed predictive structure preserved across developmental time.
```
