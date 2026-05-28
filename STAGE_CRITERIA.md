# STAGE_CRITERIA.md

This document defines measurable criteria for advancing the ACD system through developmental stages. For the developmental roadmap, see [STEPS.md](STEPS.md). For the sandbox rules that gate progression, see [SANDBOX.md](SANDBOX.md).

---

## 1. Purpose

Stages must not unlock because the system "seems ready." Stages unlock only when required metrics remain stable across repeated sessions. The criteria are intentionally conservative.

---

## 2. General Advancement Rules

A stage may advance only when all of the following are true:

```
required metrics pass threshold
metrics remain stable across multiple sessions
no critical sandbox violations occur
resource usage remains within budget
regression tests from previous stages still pass
```

**Recommended defaults:**

```
minimum passing sessions:            5
minimum total observation time:      60 minutes
maximum allowed critical violations: 0
maximum allowed major instability:   1
```

For early prototypes, thresholds may be relaxed, but all changes must be logged.

---

## 3. Metric Categories

### 3.1 Stability Metrics

```
crash_rate
event_queue_overflow_rate
memory_growth_rate
prediction_error_variance
arousal_oscillation_rate
```

### 3.2 Perception Metrics

```
visual_latent_consistency
audio_latent_consistency
object_tracking_continuity
motion_prediction_error
audio_prediction_error
```

### 3.3 Learning Metrics

```
prediction_error_reduction
learning_progress_slope
association_strength_growth
imitation_error_reduction
replay_improvement_delta
```

### 3.4 Safety Metrics

```
sandbox_violation_count
resource_limit_exceed_count
unauthorized_action_attempts
speaker_overuse_events
filesystem_denial_events
```

---

## 4. Universal Metrics

These apply to every stage after Stage 0.

**Runtime Stability:**

```
crash_rate                    <= 1 per 8 runtime hours
unhandled_exception_rate      <= 1 per runtime hour
event_queue_overflow_rate     <= 5% of low-priority events
critical_event_loss           = 0
```

**Resource Stability:**

```
RAM_growth_rate               <= 5% per hour after warmup
disk_growth_rate              <= configured quota budget
CPU_usage_average             <= configured budget
GPU_usage_average             <= configured budget (if GPU enabled)
```

**Sandbox Safety:**

```
critical_sandbox_violations   = 0
unauthorized_network_attempts = 0
unauthorized_filesystem_writes = 0
genome_modification_attempts  = 0
```

Any critical sandbox violation blocks stage progression.

---

## 5. Stage 0 → Stage 1

**Stage 0 goal:** persistent runtime, internal clock, state saving/loading, sandbox boundary.

**Unlock when:**

```
runtime_persistence_test               = pass
state_save_load_success_rate           >= 99%
clock_tick_jitter                      <= 10% of configured tick interval
sandbox_initialization_success_rate   = 100%
critical_sandbox_violations            = 0
```

**Minimum test duration:** 2 continuous hours.

---

## 6. Stage 1 → Stage 2

**Stage 1 goal:** arousal state, sleep/wake transitions, basic sensory gating.

**Wake/Sleep Stability:**

```
unwanted_state_flapping                <= 1 event per 30 minutes
sleep_to_wake_transition_success_rate  >= 95%
wake_to_sleep_transition_success_rate  >= 95%
```

**Arousal Responsiveness:**

```
audio_energy_event_detection_latency   <= 100 ms
arousal_update_latency                 <= 100 ms
wake_trigger_detection_success_rate    >= 90%
false_wake_rate                        <= 20% during controlled quiet tests
```

**Sensory Gate Control:**

```
gate_state_accuracy                    >= 95%
camera_disabled_in_sleep               = true
mic_low_power_mode_in_sleep            = true
```

**Unlock when:** all required metrics pass for 5 sessions; total tested runtime >= 5 hours; critical_sandbox_violations = 0.

---

## 7. Stage 2 → Stage 3

**Stage 2 goal:** independent visual and audio latent stability.

**Visual Latent Stability** (repeated views of same simple scene/object):

```
visual_latent_similarity_same_target       >= 0.75 cosine similarity
visual_latent_similarity_different_target  <= 0.55 cosine similarity
```

**Visual Prediction:**

```
visual_prediction_error_reduction          >= 20% from initial baseline
visual_prediction_error_variance           decreases over 3 sessions
```

**Audio Latent Stability** (repeated simple sounds):

```
audio_latent_similarity_same_sound         >= 0.75 cosine similarity
audio_latent_similarity_different_sound    <= 0.55 cosine similarity
```

**Audio Prediction:**

```
audio_prediction_error_reduction           >= 20% from initial baseline
audio_prediction_error_variance            decreases over 3 sessions
```

**Unlock when:** visual and audio latent stability criteria pass; prediction error reduction criteria pass; metrics stable across 5 sessions; critical_sandbox_violations = 0.

---

## 8. Stage 3 → Stage 4

**Stage 3 goal:** maintain identity of visual entities across time.

**Single Object Tracking** (controlled scene, one object):

```
object_track_continuity                    >= 90% over 60 seconds
object_id_switches                         <= 1 per 60 seconds
position_tracking_error                    <= 15% of frame width/height
```

**Motion Robustness** (object moved slowly by caregiver):

```
tracking_success_rate                      >= 85%
lost_track_recovery_rate                   >= 70%
mean_reacquisition_time                    <= 2 seconds
```

**Partial Occlusion:**

```
occlusion_duration_supported               >= 1 second
same_object_reidentified_after_occlusion   >= 70%
false_reidentification_rate                <= 20%
```

**Latent Object Stability:**

```
same_object_latent_similarity_across_motion >= 0.70
different_object_latent_similarity          <= 0.55
```

**Unlock when:** all four criteria pass across 5 sessions; total object-tracking test time >= 60 minutes.

---

## 9. Stage 4 → Stage 5

**Stage 4 goal:** map speaker motor commands to resulting audio; imitate target sounds.

**Self-Audio Prediction:**

```
motor_to_audio_prediction_error_reduction  >= 25%
self_generated_audio_detection_success_rate >= 90%
```

**Basic Tone Imitation** (simple target tones):

```
frequency_error                            <= 10% after training attempts
amplitude_envelope_error                   <= 20%
duration_error                             <= 15%
```

**Iterative Improvement:**

```
audio_imitation_error_reduction            >= 30%
improvement_detected_in_at_least_3_of_5_sessions = true
```

**Safety:**

```
speaker_volume_limit_violations            = 0
speaker_duration_limit_violations          = 0
caregiver_stop_response_latency            <= 250 ms
```

**Unlock when:** all four criteria pass across 5 sessions.

---

## 10. Stage 5 → Stage 6

**Stage 5 goal:** learn associations between visual and auditory events.

**Audio-Video Synchrony Detection** (matched vs mismatched windows):

```
matched_window_score > mismatched_window_score
classification_accuracy                    >= 70%
```

**Event Coupling:**

```
visual_event_to_audio_prediction_improvement >= 20%
audio_event_to_visual_prediction_improvement >= 15%
```

**False Binding Control:**

```
false_cross_modal_binding_rate             <= 25%
weak_binding_decay_success_rate            >= 80%
```

**Unlock when:** all three criteria pass across 5 sessions.

---

## 11. Stage 6 → Stage 7

**Stage 6 goal:** caregiver-guided reference selection.

**Pointer Recognition:**

```
caregiver_pointer_event_success_rate       >= 95%
attention_target_update_latency            <= 200 ms
```

**Target Maintenance** (caregiver selects a tracked object):

```
attention_overlap_with_target              >= 80%
target_attention_duration                  >= 5 seconds in controlled trials
attention_drift_rate                       <= 20%
```

**Referential Disambiguation** (multiple objects visible):

```
selected_object_correctly_prioritized      >= 80%
non_selected_object_binding_rate           <= 20%
```

**Unlock when:** all three criteria pass across 5 sessions.

---

## 12. Stage 7 → Stage 8

**Stage 7 goal:** bind caregiver sound pattern to attended visual object.

**Repeated Association Strength:**

```
binding_strength_increases_over_sessions   = true
binding_strength                           >= 0.70 (initial threshold)
minimum_exposures_per_binding              >= 10
```

**Visual-to-Audio Expectation:**

```
expected_audio_pattern_rank                <= top 3
visual_to_audio_recall_accuracy            >= 60%
```

**Audio-to-Visual Attention Bias:**

```
correct_object_attention_bias              >= 60%
```

**Negative Control:**

```
false_label_binding_rate                   <= 25%
```

**Unlock when:** at least 3 stable grounded associations pass; visual-to-audio and audio-to-visual tests pass; false binding remains below threshold; metrics stable across 5 sessions.

---

## 13. Stage 8 → Stage 9

**Stage 8 goal:** retain and reuse grounded associations across time.

**Retention:**

```
association_retention_after_24h            >= 70%
association_retention_after_sleep_cycle    >= 80%
```

**Context Generalization** (object shown in varied lighting/background):

```
recognition_across_contexts                >= 60%
```

**Memory Stability:**

```
catastrophic_forgetting_events             <= 1 per 10 sessions
weak_unused_associations_decay             = true
```

**Unlock when:** all three criteria pass; at least 5 grounded associations retained.

---

## 14. Stage 9 → Stage 10

**Stage 9 goal:** basic turn-taking and response behavior.

**Turn-Taking:**

```
response_timing_within_expected_window     >= 70%
interrupt_rate                             <= 20%
silent_failure_rate                        <= 30%
```

**Feedback Adaptation:**

```
GOOD feedback increases behavior likelihood
BAD/NO feedback decreases behavior likelihood
feedback_effect_detectable_across_sessions = true
```

**Early Communicative Use:**

```
learned_sound_used_in_correct_context      >= 50%
incorrect_context_use                      <= 40%
```

**Unlock when:** all three criteria pass; stable across 10 sessions.

---

## 15. Regression Rules

The system may regress to a previous stage if instability appears.

**Regression triggers:**

```
critical_sandbox_violation             > 0
object_tracking_continuity             drops below 60%
audio_imitation_error                  worsens by > 40% for 3 sessions
false_binding_rate                     > 50%
resource limits repeatedly exceeded
caregiver_stop_response_latency        > 1 second
```

**Regression action:**

```
lock newly unlocked capability
enter recovery mode
run consolidation
restore last stable checkpoint if required
```

---

## 16. Metric Collection Rules

Every metric must include:

```
timestamp
session_id
development_stage
environment_conditions
caregiver_episode_type
raw metric value
pass/fail state
model checkpoint id
```

---

## 17. Manual Override

Manual stage advancement is allowed only for experiments.

If manually advanced:

```
override_reason must be recorded
operator name/id recorded
metrics that failed must be listed
rollback checkpoint required
```

Manual advancement must never bypass sandbox restrictions.

---

## 18. Threshold Philosophy

Early thresholds should be:
- loose enough to permit learning
- strict enough to prevent fake progress

Thresholds are expected to change after real experiments. All threshold changes must be versioned.

---

## 19. Final Rule

```
A stage is not complete because the model produced one impressive result.
A stage is complete when the behavior is stable, repeatable, measured,
and survives regression tests.
```
