# MODULES.md

This document specifies the interface contracts for each module in the ACD system. For architectural principles, see [DESIGN.md](DESIGN.md). For the technology stack, see [STACK.md](STACK.md).

---

## Global Design Rule

All modules communicate through typed messages on an internal event bus.

**Recommended prototype:**
- Python `asyncio`
- Typed messages using `dataclasses` or Pydantic models
- Central pub/sub broker
- No direct cross-module mutation except through explicit state stores

**Core data types:**

```
Timestamp:      float seconds
Frame:          uint8 or float32 tensor [H, W, C]
AudioChunk:     float32 tensor [samples]
LatentVector:   float32 tensor [D]
RewardSignal:   float32 scalar
StateVector:    float32 tensor [D]
Event:          typed message with timestamp, source, payload
```

---

## Module 1: Arousal Regulation

**Purpose:** Controls sleep/wake intensity and compute budget.

**Inputs:**
```
AudioEnergyEvent
MotionEnergyEvent
CaregiverInteractionEvent
PredictionErrorEvent
SystemHealthEvent
```

**Outputs:**
```
ArousalStateEvent
SleepModeChangeEvent
ComputeBudgetEvent
SensoryGateControlEvent
```

**Internal State:**
```
arousal_level:    float [0.0, 1.0]
sleep_pressure:   float [0.0, 1.0]
fatigue_level:    float [0.0, 1.0]
novelty_pressure: float [0.0, 1.0]
current_mode:     enum(DEEP_SLEEP, LIGHT_SLEEP, WAKEFUL, FOCUSED, RECOVERY)
```

**Initialization:**
```
arousal_level = 0.1
sleep_pressure = 0.0
fatigue_level  = 0.0
current_mode   = LIGHT_SLEEP
```

---

## Module 2: Sensory Gating

**Purpose:** Controls how much raw sensory data enters the system.

**Inputs:**
```
ArousalStateEvent
ComputeBudgetEvent
RawCameraFrame
RawAudioChunk
```

**Outputs:**
```
GatedCameraFrame
GatedAudioChunk
DroppedInputEvent
```

**Internal State:**
```
camera_enabled:           bool
microphone_enabled:       bool
frame_rate_limit:         int
audio_sample_rate_limit:  int
sensory_gain:             float
```

**Initialization:**
```
camera_enabled          = false
microphone_enabled      = true
frame_rate_limit        = low
audio_sample_rate_limit = low
```

---

## Module 3: Visual Processing

**Purpose:** Learns visual latent representations from raw frames.

**Inputs:**
```
GatedCameraFrame:    tensor [H, W, C]
PreviousVisualLatent: tensor [D]
```

**Outputs:**
```
VisualLatentEvent:    tensor [D]
VisualPredictionEvent
MotionEstimateEvent
ObjectCandidateEvent
```

**Internal State:**
```
visual_encoder_weights
temporal_visual_state:  tensor [D]
recent_frame_buffer:    tensor [T, H, W, C]
visual_prediction_error: float
```

**Initialization:**
```
random small-weight encoder initialization
empty frame buffer
temporal state = zeros
```

---

## Module 4: Auditory Processing

**Purpose:** Learns acoustic latent representations from raw waveform.

**Inputs:**
```
GatedAudioChunk:      tensor [samples]
SelfGeneratedAudioEvent
```

**Outputs:**
```
AudioLatentEvent:       tensor [D]
AudioPredictionEvent
AudioEnergyEvent
SpeechLikeRhythmEvent
```

**Internal State:**
```
audio_encoder_weights
temporal_audio_state:   tensor [D]
recent_audio_buffer:    tensor [T, samples]
audio_prediction_error: float
```

**Initialization:**
```
random small-weight encoder initialization
empty audio buffer
temporal state = zeros
```

---

## Module 5: Prediction Engine

**Purpose:** Predicts future latent states and calculates prediction error.

**Inputs:**
```
VisualLatentEvent
AudioLatentEvent
CrossModalLatentEvent
MotorCommandEvent
```

**Outputs:**
```
PredictionErrorEvent
NextStatePredictionEvent
LearningProgressEvent
```

**Internal State:**
```
world_state_latent:          tensor [D]
prediction_model_weights
short_horizon_prediction_buffer
prediction_error_history
```

**Initialization:**
```
world_state_latent       = zeros
prediction_error_history = empty
```

---

## Module 6: Object Persistence

**Purpose:** Tracks stable visual entities over time without labels.

**Inputs:**
```
VisualLatentEvent
MotionEstimateEvent
ObjectCandidateEvent
```

**Outputs:**
```
TrackedObjectEvent
ObjectLostEvent
ObjectReidentifiedEvent
```

**Internal State:**
```
object_slots: list[ObjectSlot]

ObjectSlot:
  id:                   uuid
  latent_signature:     tensor [D]
  position_estimate:    tensor [x, y]
  velocity_estimate:    tensor [vx, vy]
  confidence:           float
  last_seen_timestamp:  float
```

**Initialization:**
```
object_slots = empty
```

---

## Module 7: Audio Motor

**Purpose:** Controls sound generation and learns sound imitation.

**Inputs:**
```
TargetAudioLatentEvent
AudioImitationRewardEvent
MotorExplorationCommand
```

**Outputs:**
```
MotorCommandEvent
SelfGeneratedAudioEvent
AudioAttemptEvent
```

**Internal State:**
```
sound_generator_parameters
motor_policy_weights
recent_attempts_buffer
target_audio_memory
```

**Initialization:**
```
sound generator = simple sine/noise/envelope generator
motor policy    = random exploration
```

---

## Module 8: Cross-Modal Integration

**Purpose:** Learns shared causes between audio, vision, attention, and events.

**Inputs:**
```
VisualLatentEvent
AudioLatentEvent
TrackedObjectEvent
AttentionTargetEvent
PredictionErrorEvent
CaregiverFeedbackEvent
```

**Outputs:**
```
CrossModalLatentEvent
AssociationCandidateEvent
SynchronyEvent
BindingStrengthEvent
```

**Internal State:**
```
association_graph
shared_event_latent:    tensor [D]
synchrony_history
binding_confidence_scores
```

**Initialization:**
```
association_graph    = empty
shared_event_latent  = zeros
```

---

## Module 9: Joint Attention

**Purpose:** Provides caregiver-guided referential focus.

**Inputs:**
```
CaregiverPointerEvent
TrackedObjectEvent
VisualLatentEvent
AudioLatentEvent
```

**Outputs:**
```
AttentionTargetEvent
ReferentCandidateEvent
LabelBindingAttemptEvent
```

**Internal State:**
```
current_attention_target
attention_confidence:   float
recent_referent_history
```

**Initialization:**
```
current_attention_target = none
attention_confidence     = 0.0
```

---

## Module 10: Reinforcement / Value

**Purpose:** Converts feedback and drive states into learning signals.

**Inputs:**
```
CaregiverFeedbackEvent
PredictionErrorEvent
LearningProgressEvent
SystemHealthEvent
SocialInteractionEvent
```

**Outputs:**
```
RewardSignalEvent
PenaltySignalEvent
DriveStateEvent
```

**Internal State:**
```
continuity_drive:  float
stability_drive:   float
energy_drive:      float
curiosity_drive:   float
social_drive:      float
integrity_drive:   float
reward_history
```

**Initialization:**
```
all drives    = neutral baseline
reward_history = empty
```

---

## Module 11: Memory / Consolidation

**Purpose:** Stores, compresses, replays, and prunes experience.

**Inputs:**
```
VisualLatentEvent
AudioLatentEvent
CrossModalLatentEvent
RewardSignalEvent
TrackedObjectEvent
AssociationCandidateEvent
```

**Outputs:**
```
ReplayEvent
MemoryRecallEvent
PruningEvent
ConsolidatedAssociationEvent
```

**Internal State:**
```
working_memory_buffer
episodic_memory_store
associative_memory_graph
procedural_memory_store
decay_scores
```

**Initialization:**
```
empty working memory
empty episodic store
empty association graph
```

---

## Module 12: Sandbox / Capability Manager

**Purpose:** Enforces physics-like boundaries on agent actions.

**Inputs:**
```
ActionRequestEvent
DevelopmentStageEvent
IntegrityCheckEvent
```

**Outputs:**
```
ActionApprovedEvent
ActionDeniedEvent
CapabilityChangedEvent
ViolationEvent
```

**Internal State:**
```
allowed_capabilities
current_development_stage
violation_history
privilege_level
```

**Initialization:**
```
stage             = 0
privilege_level   = infant
allowed_capabilities = minimal sensory/audio output only
```

---

## Module 13: Development Stage Manager

**Purpose:** Controls developmental unlocks based on measured stability.

**Inputs:**
```
PerformanceMetricEvent
StabilityMetricEvent
CapabilityRequestEvent
```

**Outputs:**
```
DevelopmentStageEvent
CapabilityUnlockEvent
RegressionEvent
```

**Internal State:**
```
current_stage:        int
stage_metrics
unlock_requirements
regression_conditions
```

**Initialization:**
```
current_stage             = 0
all higher capabilities   = locked
```

---

## Module 14: Caregiver Interface

**Purpose:** Allows human-guided teaching without injecting datasets.

**Inputs:**
```
UserPointerInput
UserFeedbackInput
UserAudioInput
UserSessionControl
```

**Outputs:**
```
CaregiverPointerEvent
CaregiverFeedbackEvent
CaregiverInteractionEvent
TeachingEpisodeEvent
```

**Internal State:**
```
current_session_id
feedback_history
pointer_history
teaching_episode_buffer
```

**Initialization:**
```
no active teaching episode
feedback_history = empty
```

---

## Communication Pattern

Recommended message flow:

```
Raw Sensors
  -> Sensory Gate
  -> Visual / Audio Processing
  -> Prediction Engine
  -> Object Persistence / Audio Motor / Cross-Modal Integration
  -> Reinforcement + Memory
  -> Development Stage Manager
```

- All modules publish events to the bus.
- Modules subscribe only to the event types they require.
- Avoid direct circular calls.

---

## Persistence Requirements

**Persistent across sessions:**
```
drive state
development stage
learned model weights
association graph
memory summaries
object identity statistics
audio motor mappings
```

**Ephemeral (in-process only):**
```
raw frame buffers
raw audio buffers
temporary prediction states
short-term attention states
```

Raw audio/video must not be stored permanently by default.

---

## Initialization Order

1. Sandbox / Capability Manager
2. State Store
3. Event Bus
4. Arousal Regulation
5. Sensory Gating
6. Sensor Input Modules
7. Visual and Audio Processing
8. Prediction Engine
9. Reinforcement / Value Module
10. Memory / Consolidation Module
11. Development Stage Manager
12. Caregiver Interface

---

## First Implementation Rule

Do not build all modules fully upfront.

Build thin interfaces first. Each module should initially:

- accept typed input
- maintain internal state
- emit typed output
- log behavior
- allow replacement later

**The first goal is architecture stability, not intelligence.**
