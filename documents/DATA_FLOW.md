# DATA_FLOW.md

This document defines the data flow architecture for the ACD system. For module interface specs, see [MODULES.md](MODULES.md). For the technology stack, see [STACK.md](STACK.md). For architectural principles, see [DESIGN.md](DESIGN.md).

---

## 1. Overview

The ACD system uses an asynchronous, event-driven architecture. The system must process real-time audio and video while also supporting slower background learning, memory consolidation, reinforcement updates, and developmental state management.

The architecture separates processing into three timing classes:

**1. Real-time sensory loops**
- audio capture
- video capture
- sensory gating
- low-latency arousal signals

**2. Near-real-time learning loops**
- visual encoding
- audio encoding
- prediction error calculation
- object tracking
- sound imitation feedback

**3. Background developmental loops**
- replay
- consolidation
- pruning
- model checkpointing
- long-term association strengthening

The system must not block real-time sensory capture while training or consolidation tasks are running.

---

## 2. Communication Model

### 2.1 Event-Driven Core

All modules communicate through an internal event bus. Modules do not call each other directly. Instead:

```
Module A publishes Event X
Module B subscribes to Event X
Module B processes event
Module B publishes Event Y
```

This keeps modules replaceable and prevents tightly coupled logic.

### 2.2 Recommended Prototype Implementation

```
Python asyncio event bus
Typed dataclass or Pydantic events
Async queues per subscriber
Shared read-only config object
SQLite / state store for persistence
PyTorch models for learning modules
```

**Core rule: real-time capture must never wait for model training.**

If queues overflow, low-priority events are dropped before real-time capture is blocked.

---

## 3. System Diagram

```
                         ┌────────────────────────┐
                         │   Caregiver Interface   │
                         │ pointer / feedback / UI │
                         └───────────┬────────────┘
                                     │
                                     ▼
┌──────────────┐        ┌────────────────────────┐
│ Microphone   │───────▶│     Sensory Gate        │───────┐
└──────────────┘        │ audio/video throttling  │       │
                        └───────────┬────────────┘       │
┌──────────────┐                    │                     │
│ Camera       │────────────────────┘                     │
└──────────────┘                                          │
                                                          ▼
         ┌──────────────────────┐       ┌──────────────────────┐
         │   Auditory Encoder   │       │    Visual Encoder     │
         │ raw audio → latent   │       │ raw pixels → latent   │
         └──────────┬───────────┘       └──────────┬───────────┘
                    │                              │
                    ▼                              ▼
         ┌──────────────────────┐       ┌──────────────────────┐
         │  Audio Prediction    │       │  Visual Prediction    │
         │  next audio latent   │       │  next visual latent   │
         └──────────┬───────────┘       └──────────┬───────────┘
                    │                              │
                    ▼                              ▼
         ┌──────────────────────┐       ┌──────────────────────┐
         │  Audio Motor Module  │       │  Object Persistence   │
         │  babble / imitate    │       │  track object identity│
         └──────────┬───────────┘       └──────────┬───────────┘
                    │                              │
                    └──────────────┬───────────────┘
                                   ▼
                        ┌──────────────────────┐
                        │  Cross-Modal Bridge   │
                        │  shared event latent  │
                        └──────────┬───────────┘
                                   │
                                   ▼
                        ┌──────────────────────┐
                        │ Reinforcement / Value │
                        │  drives + reward      │
                        └──────────┬───────────┘
                                   │
                                   ▼
                        ┌──────────────────────┐
                        │ Memory / Consolidation│
                        │  replay / prune / save│
                        └──────────┬───────────┘
                                   │
                                   ▼
                        ┌──────────────────────┐
                        │  Development Manager  │
                        │  stage unlocks        │
                        └──────────────────────┘


          ┌──────────────────────────────────────────────┐
          │          Arousal / Regulation Layer           │
          │  sleep, wake, compute budget, sensory gain    │
          └──────────────────────────────────────────────┘
```

The Arousal / Regulation Layer observes events from the whole system and publishes control events back into the sensory gate, learning modules, and development manager.

---

## 4. Main Event Flows

### 4.1 Audio Flow

```
Microphone
  → RawAudioChunk
  → SensoryGate
  → GatedAudioChunk
  → AuditoryEncoder
  → AudioLatentEvent
  → AudioPredictionModule
  → PredictionErrorEvent
  → ReinforcementModule
  → MemoryModule
```

**Imitation sub-flow:**

```
CaregiverAudioInput
  → TargetAudioLatentEvent
  → AudioMotorModule
  → MotorCommandEvent
  → SpeakerOutput
  → SelfGeneratedAudioEvent
  → AuditoryEncoder
  → AudioSimilarityErrorEvent
  → ReinforcementModule
```

### 4.2 Vision Flow

```
Camera
  → RawCameraFrame
  → SensoryGate
  → GatedCameraFrame
  → VisualEncoder
  → VisualLatentEvent
  → VisualPredictionModule
  → PredictionErrorEvent
  → ObjectPersistenceModule
  → TrackedObjectEvent
  → MemoryModule
```

### 4.3 Cross-Modal Flow

```
VisualLatentEvent
AudioLatentEvent
TrackedObjectEvent
CaregiverPointerEvent
CaregiverFeedbackEvent
  → CrossModalIntegrationModule
  → AssociationCandidateEvent
  → BindingStrengthEvent
  → MemoryModule
  → ReinforcementModule
```

### 4.4 Regulation Flow

```
AudioEnergyEvent
MotionEnergyEvent
PredictionErrorEvent
SystemHealthEvent
CaregiverInteractionEvent
  → ArousalRegulationModule
  → ArousalStateEvent
  → ComputeBudgetEvent
  → SensoryGateControlEvent
  → SleepModeChangeEvent
```

---

## 5. Processing Model

### 5.1 Synchronous vs Asynchronous

The system is primarily asynchronous. Use synchronous processing only inside small module-local functions.

```
Async:
  - sensor capture
  - event routing
  - training loops
  - memory consolidation

Sync:
  - calculating audio energy for one chunk
  - encoding one frame
  - updating one object slot
```

### 5.2 Priority Classes

```
Priority 0:  critical safety / shutdown / sandbox violation
Priority 1:  real-time audio capture
Priority 2:  real-time visual capture
Priority 3:  arousal and gating
Priority 4:  prediction and tracking
Priority 5:  reinforcement and memory
Priority 6:  consolidation and replay
Priority 7:  logging and analytics
```

If the system is overloaded, lower-priority events are dropped or delayed first.

---

## 6. Latency and Throughput Budgets

These are prototype targets, not final biological constraints.

### Audio Capture

```
Sample rate:                     16 kHz minimum
Chunk size:                      20–50 ms
Target processing latency:       < 50 ms for energy/arousal
Target imitation feedback latency: < 200 ms
```

Audio arousal processing must be extremely lightweight.

### Video Capture

```
Resolution:                 start at 160×120 or 224×224
Frame rate:                 5–15 FPS initially
Target processing latency:  < 100 ms per frame
```

Do not start with HD video. High-resolution vision should be introduced only after stable low-resolution tracking works.

### Visual Prediction

```
Initial frame rate:     5 FPS
Prediction horizon:     1–5 frames
Latency target:         < 200 ms
```

### Cross-Modal Bridge

```
Temporal window:         0.5–3 seconds
Association update rate: 1–5 Hz
Latency target:          < 500 ms
```

Cross-modal binding does not need millisecond precision at first.

### Memory and Consolidation

```
Working memory buffer:    seconds to minutes
Episodic compression:     every few minutes or at session end
Deep consolidation:       during sleep modes
Latency:                  non-real-time
```

---

## 7. Backpressure and Dropping Rules

### 7.1 Queue Limits

Each event queue should have a maximum size:

```
audio_queue:    small, high priority
video_queue:    small, drop old frames
memory_queue:   medium
logging_queue:  large but lossy
training_queue: bounded
```

### 7.2 Dropping Policy

If overloaded, degrade in this order:

1. Drop logs first
2. Drop old video frames
3. Delay consolidation
4. Skip non-critical prediction updates
5. Reduce camera FPS
6. Reduce audio feature detail
7. Enter recovery mode

Never block:
- audio arousal monitoring
- sandbox control
- shutdown handling

---

## 8. Timing Loops

### 8.1 Always-On Loop

```
Frequency:       10–50 Hz
Responsibilities:
  - audio energy monitoring
  - arousal level update
  - sleep/wake state
  - sandbox health
```

### 8.2 Vision Loop

```
Frequency:       5–15 FPS initially (when sensory gate allows)
Responsibilities:
  - frame acquisition
  - visual encoding
  - motion estimation
  - object slot update
```

### 8.3 Audio Learning Loop

```
Frequency:       chunk-based, 20–50 ms (during wakeful and focused states)
Responsibilities:
  - audio latent update
  - target matching
  - imitation error calculation
```

### 8.4 Prediction Loop

```
Frequency:       1–10 Hz initially (during wakeful and sleep/replay states)
Responsibilities:
  - latent prediction
  - error calculation
  - learning progress tracking
```

### 8.5 Consolidation Loop

```
Frequency:       background / scheduled (mostly during sleep modes)
Responsibilities:
  - replay recent experience
  - prune weak associations
  - checkpoint models
  - compress memory
```

---

## 9. Event Message Examples

**RawAudioChunk**
```
type:        RawAudioChunk
timestamp:   float
sample_rate: int
samples:     float32 tensor [N]
source:      microphone
```

**GatedCameraFrame**
```
type:        GatedCameraFrame
timestamp:   float
frame_id:    int
resolution:  [H, W]
frame:       uint8 tensor [H, W, C]
gate_level:  float
```

**VisualLatentEvent**
```
type:             VisualLatentEvent
timestamp:        float
frame_id:         int
latent:           float32 tensor [D]
prediction_error: optional float
```

**AudioLatentEvent**
```
type:      AudioLatentEvent
timestamp: float
chunk_id:  int
latent:    float32 tensor [D]
energy:    float
```

**TrackedObjectEvent**
```
type:             TrackedObjectEvent
timestamp:        float
object_id:        string
position:         [x, y]
velocity:         [vx, vy]
latent_signature: float32 tensor [D]
confidence:       float
```

**CrossModalAssociationEvent**
```
type:                CrossModalAssociationEvent
timestamp:           float
visual_object_id:    optional string
audio_pattern_id:    optional string
attention_target_id: optional string
binding_strength:    float
confidence:          float
```

---

## 10. Threading / Process Recommendation

For the first prototype:

```
Main process:
  - event bus
  - state store
  - module orchestration

Async tasks:
  - audio capture
  - video capture
  - arousal loop
  - visual processing
  - audio processing
  - prediction loop
  - memory loop

Optional separate process:
  - heavy PyTorch training
  - replay / consolidation
```

Heavy ML training can block Python event loops. If that becomes an issue, move training into a separate worker process.

---

## 11. GPU Usage Strategy

**Use CPU for:**
- audio energy
- simple gating
- queue management
- basic motion detection
- event routing

**Use GPU for:**
- visual encoder
- audio encoder
- predictive model training
- replay batches

Batch where possible, especially during sleep/consolidation. Do not send every raw frame or audio chunk to the GPU immediately.

---

## 12. Failure Modes

### 12.1 Real-Time Overload

**Symptoms:** audio lag, video backlog, delayed arousal response

**Response:**
- drop old video frames
- reduce FPS
- disable non-critical training
- enter recovery mode

### 12.2 Event Storm

**Symptoms:** too many events from one module, queue saturation

**Response:**
- rate-limit the offending module
- collapse repeated events
- increase arousal only once per window

### 12.3 Latent Instability

**Symptoms:** object identity constantly changes, predictions never improve, associations fail to stabilize

**Response:**
- reduce input complexity
- lower frame rate
- simplify environment
- increase replay
- freeze some model components temporarily

### 12.4 Cross-Modal False Binding

**Symptoms:** system associates sound with wrong object, binds labels to whole scene

**Response:**
- require joint attention signal before binding
- narrow temporal window
- require repeated episodes before strengthening
- decay weak associations aggressively

---

## 13. First Data Flow Milestones

**Milestone 1:**
```
Camera → Sensory Gate → Visual Encoder → Object Persistence → Memory
```
Success: a single moving object is tracked consistently across frames.

**Milestone 2:**
```
Microphone → Auditory Encoder → Audio Motor → Speaker → Microphone → Error Signal
```
Success: system can iteratively reduce the difference between a target sound and its produced sound.

**Milestone 3:**
```
Tracked Object + Caregiver Sound + Attention Cue → Cross-Modal Association
```
Success: system forms a repeatable association between an attended object and a sound pattern.
