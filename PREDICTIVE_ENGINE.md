# PREDICTIVE_ENGINE.md

This document specifies the predictive learning engine for the ACD system. For data flow context, see [DATA_FLOW.md](DATA_FLOW.md). For the technology stack, see [STACK.md](STACK.md). For architectural principles, see [DESIGN.md](DESIGN.md).

---

## 1. Decision

The first predictive learning engine will be a:

```
Latent Predictive World Model
using a JEPA-style self-supervised objective
```

This means the system predicts future or missing latent representations — not raw pixels, raw waveform samples, or text tokens.

The model learns:

```
current latent state + context + action
    → predicted future latent state
```

It does not initially generate images, speech, or language.

---

## 2. Why JEPA-Style Latent Prediction

JEPA predicts representations rather than reconstructing raw inputs. I-JEPA demonstrated this approach for self-supervised image representation learning by predicting target block representations from context block representations, rather than reconstructing pixels.

This fits ACD better than raw reconstruction because the goal is not photographic memory. The goal is stable internal structure.

The agent should learn:
- what matters
- what persists
- what changes
- what predicts future experience

Not:
- every pixel
- every waveform detail

---

## 3. Why Not Diffusion First

Diffusion models are powerful generative models, but they are the wrong first primitive.

Reasons:
- too compute-heavy
- too data-hungry
- optimized for generation quality, not infant-like representation stability
- would encourage reconstructing surface detail before learning persistent structure

For this project, generation comes later. Prediction and stability come first.

---

## 4. Why Not Masked Autoencoder First

MAE-style reconstruction has proven effective in scalable self-supervised vision learning. However, it is not ideal as the first core objective because:
- it encourages pixel-level detail reconstruction
- it can learn texture without object persistence
- it is less naturally tied to action and temporal prediction
- it is not enough for audio-vision event binding

MAE can be used later as an auxiliary task, but not as the primary cognitive engine.

---

## 5. Why Not Dreamer First

DreamerV3 is a strong world-model reinforcement learning system that learns a model of the environment and improves behavior by imagining future scenarios. Dreamer is highly relevant later, especially once the agent has:
- action choices
- sandbox tasks
- stable perception
- reward signals
- enough motor agency to plan

But it is too advanced for the first infant stage. The first system does not need full imagined rollout planning. It needs stable perception and prediction.

Dreamer-like components can be introduced later as the planning/world-model layer.

---

## 6. Core Architecture

The predictive engine is split into five parts:

```
1. Encoder
2. Context State Model
3. Predictor
4. Target Encoder
5. Loss / Learning Signal
```

### 6.1 Encoder

Converts raw sensory input into latent representations.

**Vision Encoder**

Input:
```
GatedCameraFrame: float32 tensor [B, C, H, W]
```

Output:
```
VisualLatent: float32 tensor [B, Dv]
```

Prototype: small CNN encoder
Later: ConvNeXt / small ViT / slot-based object encoder

**Audio Encoder**

Input:
```
GatedAudioChunk: float32 tensor [B, samples]
```
or:
```
Spectrogram: float32 tensor [B, F, T]
```

Output:
```
AudioLatent: float32 tensor [B, Da]
```

Prototype: 1D Conv encoder or spectrogram CNN
Later: audio transformer or state-space audio encoder

### 6.2 Context State Model

Maintains temporal context.

Input:
```
previous_state
current_visual_latent
current_audio_latent
optional_motor_action
```

Output:
```
ContextState: float32 tensor [B, Dc]
```

Prototype: GRU or small recurrent state model
Later: state-space model, recurrent world model, or transformer memory

**Rule:** Do not begin with a large transformer. The infant stage requires stability and interpretability, not maximum scale.

### 6.3 Predictor

Predicts future or hidden latent states.

Input:
```
ContextState
prediction_horizon
modality_token
```

Output:
```
PredictedLatent: float32 tensor [B, D]
```

Examples:
```
predict visual latent at t+1
predict audio latent at t+1
predict attended object latent after movement
predict audio latent associated with current visual event
```

### 6.4 Target Encoder

The target encoder produces the latent state that the predictor tries to match.

The target encoder should be updated more slowly than the online encoder.

Recommended:
```
EMA target encoder
```

This improves stability and prevents collapse.

### 6.5 Loss Function

Primary loss:
```
latent prediction loss
```

Recommended options:
```
cosine distance
smooth L1 loss
variance/covariance regularization
contrastive loss where useful
```

The system should avoid representation collapse. Use auxiliary anti-collapse terms if needed.

---

## 7. First Predictive Objectives

### Objective 1: Visual Temporal Prediction

Task:
```
given visual latent at time t
predict visual latent at time t+1
```

Purpose: temporal stability, motion awareness, object persistence foundation.

### Objective 2: Audio Temporal Prediction

Task:
```
given audio latent at time t
predict audio latent at time t+1
```

Purpose: rhythm learning, acoustic continuity, speech-like structure foundation.

### Objective 3: Cross-Modal Synchrony

Task:
```
given visual context and audio context
predict whether they belong to the same time window
```

Purpose: audio/video binding, event detection, shared-cause discovery.

### Objective 4: Action-Conditioned Audio Prediction

Task:
```
given motor command to speaker
predict resulting audio latent
```

Purpose: babbling, self-generated sound modeling, speech imitation foundation.

### Objective 5: Attention-Conditioned Association

Task:
```
given attended visual object latent + caregiver audio pattern
predict repeated association strength
```

Purpose: word grounding, joint attention, label binding.

This comes later, after object tracking exists.

---

## 8. Model Progression

**Version 0: Minimal Latent Predictor**
```
CNN vision encoder
Conv1D audio encoder
GRU context model
MLP predictor
EMA target encoder
```
Goal: prove prediction error decreases over time.

**Version 1: Object-Aware Predictor**

Adds:
```
object slots
tracked object latents
per-object prediction
```
Goal: stable object identity across frames.

**Version 2: Audio Motor Predictor**

Adds:
```
motor command embeddings
self-generated audio prediction
audio imitation reward
```
Goal: learn controllable sound output.

**Version 3: Cross-Modal Event Predictor**

Adds:
```
shared event latent
audio-video synchrony prediction
attention-conditioned binding
```
Goal: bridge vision and audio.

**Version 4: Dreamer-Like World Model**

Adds:
```
imagination rollouts
latent planning
reward prediction
policy learning
```
This stage is only appropriate after stable sensorimotor representations exist.

---

## 9. Training Schedule

### Awake Mode

During wakeful interaction:
```
online encoding
short-horizon prediction
prediction error logging
limited lightweight updates
```

Keep training light to preserve real-time responsiveness.

### Sleep Mode

During sleep/consolidation:
```
batch replay
encoder refinement
predictor training
association strengthening
pruning
checkpointing
```

Most heavy learning happens here.

---

## 10. Input and Output Shapes

**Vision**

Initial:
```
frame:         [B, 3, 160, 120] or [B, 3, 224, 224]
visual_latent: [B, 128]
```

Later:
```
visual_latent: [B, 256–1024]
object_slots:  [B, N, D]
```

**Audio**

Initial:
```
audio_chunk:   [B, 800] at 16 kHz for 50 ms
audio_latent:  [B, 128]
```

or spectrogram:
```
spectrogram:   [B, F, T]
audio_latent:  [B, 128]
```

**Context State**

Initial:
```
context_state: [B, 256]
```

Later:
```
context_state: [B, 512–2048]
```

---

## 11. Collapse Prevention

Self-supervised systems can collapse into useless representations. Use:

```
EMA target encoder
variance regularization
stop-gradient target branch
prediction across time
negative samples for synchrony tasks
replay diversity
```

Do not train only on static scenes. The infant must experience movement, change, and repeated interaction.

---

## 12. First Success Criteria

The predictive engine is working if:

| Domain | Criterion |
|---|---|
| Basic | prediction error decreases over time |
| Visual | same object produces stable latent signature across frames |
| Audio | same sound produces stable latent signature across repetitions |
| Cross-modal | matched audio/video windows score higher than mismatched windows |
| Motor | speaker motor commands become predictably linked to resulting audio latents |

---

## 13. Final Decision Summary

The ACD predictive engine starts as:

```
JEPA-style latent predictive learning
with recurrent temporal context
and slow-moving target encoders
```

It is not initially:

```
diffusion model
large transformer
pixel reconstruction MAE
full Dreamer-style planner
```

Those may become useful later. The first task is not imagination. The first task is stable perception.
