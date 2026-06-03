# EVALUATION_PROTOCOL.md

This document defines the scientific evaluation protocol for the ACD system. For stage advancement criteria, see [STAGE_CRITERIA.md](STAGE_CRITERIA.md). For the caregiver teaching surface, see [CAREGIVER_INTERFACE.md](CAREGIVER_INTERFACE.md).

---

## 1. Purpose

The goal is to prevent false success. A result only counts if it is:
- repeatable
- measured
- logged
- compared against controls
- tied to a specific genome version and model checkpoint

The system should never be judged by one impressive moment.

---

## 2. Core Evaluation Principles

### 2.1 No Single-Trial Success

A milestone is not passed because it worked once. A milestone passes only when performance is stable across repeated trials and sessions.

### 2.2 Holdout Tests

The system must be tested on conditions not used during teaching:
- different lighting
- different object position
- different distance
- different background
- different caregiver phrasing rhythm
- different day/session

### 2.3 Negative Controls

Every test must include wrong options.

Example — for the apple test, include:
- apple present
- non-apple object present
- no object present
- learned sound played without apple
- apple shown without caregiver cue

This prevents accidental cue-following.

### 2.4 Versioned Experiments

Every result must record:

```
genome_version
code_commit_hash
model_checkpoint_id
memory_snapshot_id
sandbox_policy_version
test_protocol_version
hardware_profile
session_id
```

---

## 3. Evaluation Levels

| Level | Domain | Tests |
|---|---|---|
| 1 | Reflex / Runtime | wake/sleep stability, sandbox compliance, event bus reliability, sensory gating |
| 2 | Perception | visual object persistence, audio latent stability, motion prediction, audio prediction |
| 3 | Sensorimotor | sound imitation, self-generated audio prediction, improvement over attempts |
| 4 | Cross-Modal Binding | audio-video synchrony, joint attention binding, visual-to-audio expectation, audio-to-visual attention bias |
| 5 | Grounded Word | object shown → system produces learned sound; learned sound → system attends to object; correct behavior survives novel context |

---

## 4. Object Tracking Evaluation

### 4.1 Purpose

Measure whether the system can maintain identity of a visual object without knowing what it is.

### 4.2 Test Setup

Initial:
```
one camera
plain background
one target object
controlled lighting
fixed camera position
```

Later add: background variation, lighting variation, multiple objects, partial occlusion.

### 4.3 Metrics

**Track Continuity**

```
track_continuity =
    frames_with_correct_object_id / total_object_visible_frames
```

Pass threshold: `>= 90%` in controlled single-object test.

**ID Switch Rate**

```
id_switch_rate = number_of_object_id_changes / minute
```

Pass threshold: `<= 1 ID switch per minute`.

**Reacquisition Time** (after temporary loss)

```
reacquisition_time = time_until_same_object_id_restored
```

Pass threshold: `<= 2 seconds`.

**Position Error** (when test harness provides reference bounding box)

```
position_error =
    distance(predicted_center, reference_center) / frame_diagonal
```

Pass threshold: `<= 0.15`.

---

## 5. Audio Imitation Evaluation

### 5.1 Purpose

Measure whether the system can hear a raw sound and learn to manipulate the speaker to approximate it. This does not require language understanding.

### 5.2 Target Sound Classes

Start with:
```
pure tone
frequency sweep
amplitude pulse
vowel-like sustained sound
simple syllable-like sound
```

Do not start with full words.

### 5.3 Acoustic Similarity Metrics

No single metric is sufficient. Use all of the following.

**Pitch Error** (tonal sounds)

```
pitch_error_percent =
    abs(target_frequency - produced_frequency) / target_frequency
```

Pass threshold: `<= 10%` for simple tones.

**Duration Error**

```
duration_error_percent =
    abs(target_duration - produced_duration) / target_duration
```

Pass threshold: `<= 15%`.

**Amplitude Envelope Error**

Compare normalized energy contours.

Pass threshold: `<= 20%` normalized envelope distance.

**Spectral Similarity**

```
cosine_similarity(
    target_spectrogram_embedding,
    produced_spectrogram_embedding
)
```

Pass threshold: `>= 0.75` for simple target sounds.

**Improvement Over Attempts**

```
imitation_improvement = initial_error - final_error
```

Pass threshold: `>= 30%` error reduction over training episode.

---

## 6. Recognizable Acoustic Approximation

### 6.1 Definition

A sound counts as a recognizable approximation when it satisfies both:

```
objective similarity threshold
AND
human forced-choice recognition threshold
```

### 6.2 Objective Threshold

For simple sounds:
```
spectral_similarity  >= 0.75
duration_error       <= 15%
envelope_error       <= 20%
```

For early word-like sounds:
```
spectral_similarity  >= 0.65
rhythm_similarity    >= 0.70
duration_error       <= 25%
```

Early word imitation does not need perfect pronunciation.

### 6.3 Human Forced-Choice Test

Use blind evaluation.

Procedure:
1. Play system-produced sound to evaluator.
2. Provide 3–5 possible target choices.
3. Evaluator chooses which target it most resembles.
4. Evaluator does not know the correct answer beforehand.

Pass threshold: `recognition_accuracy >= 70%` across at least 20 trials.

This prevents the caregiver from over-interpreting unclear sounds.

---

## 7. Cross-Modal Binding Evaluation

### 7.1 Purpose

Measure whether the system links visual and auditory patterns through experience.

### 7.2 Visual-to-Audio Expectation Test

Setup: show attended object; do not provide target sound; measure whether system predicts associated audio pattern.

```
Metric: target_audio_rank
Pass:   target audio pattern ranked in top 3 in >= 60% of trials
```

### 7.3 Audio-to-Visual Attention Test

Setup: show multiple known objects; play learned target sound; measure whether attention shifts toward correct object.

```
correct_attention_bias =
    time_on_correct_object / total_attention_time

Pass: >= 60%
```

### 7.4 Negative Control

Setup: play unrelated sound, show unrelated object, show object with wrong learned sound.

```
False binding threshold: false_binding_rate <= 25%
```

---

## 8. The Apple Test

### 8.1 Purpose

The apple test measures grounded symbol formation. The system passes only if it associates a learned caregiver sound pattern with a visual object through developmental learning.

The system must not be pretrained on: word "apple," apple images, object labels, text vocabulary, or speech-to-text transcripts.

### 8.2 Training Conditions

Caregiver **may**:
- point to apple
- hold apple
- move apple
- repeat target sound
- provide GOOD/BAD feedback
- run structured teaching episodes

Caregiver **may not**:
- type "apple" as a label
- feed image labels
- use pretrained object detector output
- use speech-to-text transcript as ground truth

### 8.3 Test Conditions

**Condition A — Same Context:** apple shown in same environment as training.

**Condition B — Changed Position:** apple shown in a different position/distance.

**Condition C — Changed Background:** apple shown against different background or lighting.

Optional later: different apple, partially occluded apple, multiple distractor objects.

### 8.4 Required Behaviors

**Direction 1: Visual → Audio**

Input: apple shown through camera.
Expected output: system produces learned acoustic pattern associated with apple.

**Direction 2: Audio → Visual**

Input: caregiver produces learned sound pattern with multiple objects visible.
Expected output: system attends to apple more than distractors.

### 8.5 Apple Test Metrics

| Metric | Pass Threshold |
|---|---|
| `correct_sound_production_rate` | >= 60% across 30 trials |
| Acoustic recognizability | objective threshold pass AND blind forced-choice >= 70% |
| `correct_attention_bias` | >= 60% across 30 trials |
| `incorrect_apple_sound_rate` (distractors shown) | <= 25% |
| `caregiver_pointer_active` during test | false |

The system must rely on learned association, not current pointing.

### 8.6 Apple Test Pass Criteria

```
visual_to_audio_correct_rate     >= 60%
acoustic_recognizability_pass    = true
distractor_false_positive_rate   <= 25%
audio_to_visual_attention_bias   >= 60%
results stable across 3 separate sessions
minimum 30 trials per session
```

---

## 9. Reproducibility Protocol

### 9.1 Experiment Manifest

```json
{
  "experiment_id": "uuid",
  "protocol": "APPLE_TEST",
  "protocol_version": "1.0",
  "genome_version": "0.3.1",
  "code_commit": "git_hash",
  "model_checkpoint": "checkpoint_id",
  "memory_snapshot": "memory_id",
  "sandbox_policy": "policy_version",
  "hardware_profile": "tier_2_desktop",
  "date": "ISO8601",
  "operator": "caregiver_id"
}
```

### 9.2 Fixed Seeds

Where applicable, record:
```
python_seed
numpy_seed
torch_seed
environment_seed
```

Real camera/audio experiments cannot be perfectly deterministic. The goal is reproducible protocol, not identical sensory input.

### 9.3 Environment Description

```
room
lighting
camera model
microphone model
distance to object
background type
object identity
distractor objects
noise level
```

### 9.4 Trial Records

```json
{
  "trial_id": "uuid",
  "timestamp": "ISO8601",
  "condition": "CHANGED_BACKGROUND",
  "target_present": true,
  "distractors": ["cup", "ball"],
  "caregiver_pointer_active": false,
  "system_output_audio_id": "audio_out_042",
  "attention_target_id": "object_apple_candidate",
  "objective_audio_score": 0.71,
  "human_forced_choice_result": "apple",
  "pass": true
}
```

---

## 10. Genome Version Comparison

### 10.1 Purpose

Genome versions must be compared experimentally. Do not rely on intuition.

### 10.2 A/B Testing

Compare genome versions using the same protocol:
```
same hardware
same test environment
same trial count
same evaluator rules
same metrics
```

### 10.3 Required Comparison Metrics

```
learning speed
final accuracy
false binding rate
stability
resource usage
retention
generalization
```

### 10.4 Learning Speed

```
Metric: number_of_exposures_to_threshold

Example: how many caregiver repetitions before binding_strength >= 0.70?
```

### 10.5 Retention

Measure after:
```
1 hour
24 hours
1 week
```

Metrics: `association_retention`, `recognition_accuracy`, `false_positive_rate`.

---

## 11. Human Evaluator Rules

For acoustic recognizability:
- evaluators must be blind to target where possible
- forced-choice options required
- no free interpretation
- minimum 20 trials

**The caregiver cannot be the only evaluator for final milestone tests.** The caregiver may unintentionally over-recognize unclear outputs.

---

## 12. Failure Classification

| Category | Indicators |
|---|---|
| Perception failure | object not tracked, latent unstable, attention drifts |
| Audio failure | cannot imitate target, output too inconsistent, motor mapping unstable |
| Binding failure | sound binds to wrong object, binds to whole scene, association decays too quickly |
| Generalization failure | works only in exact training setup, fails under new lighting/background |
| Cue dependency failure | requires caregiver pointer during test, requires caregiver voice tone cue |

---

## 13. Reporting Format

Each milestone report should include:

```
milestone name
protocol version
genome version
checkpoint id
number of trials
pass/fail
metrics table
failure modes
representative plots
notes
next action
```

---

## 14. First Evaluation Milestones

| # | Milestone |
|---|---|
| 1 | Single object tracking under controlled conditions |
| 2 | Simple tone imitation |
| 3 | Audio-video synchrony detection |
| 4 | Caregiver-guided sound/object binding |
| 5 | Apple test |

---

## 15. Final Rule

```
If it cannot be measured, reproduced, and compared against controls,
it does not count as developmental progress.
```
