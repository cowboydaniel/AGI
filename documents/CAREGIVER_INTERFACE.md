# CAREGIVER_INTERFACE.md

This document specifies the caregiver interface for the ACD system. For the module that produces caregiver events, see [MODULES.md](MODULES.md) (Module 14). For data flow context, see [DATA_FLOW.md](DATA_FLOW.md).

---

## 1. Purpose

The caregiver interface is the human teaching surface for the ACD system.

It allows a human caregiver to:
- guide attention
- label experiences
- provide approval/disapproval
- run teaching episodes
- observe what the system is attending to
- avoid injecting datasets or preloaded knowledge

The interface is not a chatbot UI. It is closer to a parent interacting with an infant through pointing, repetition, praise, correction, and controlled exposure.

---

## 2. Design Philosophy

The caregiver does not upload knowledge. The caregiver creates structured experiences.

The system must learn through:
- raw visual input
- raw audio input
- attention cues
- reinforcement
- repetition
- prediction error reduction

The caregiver interface must provide:
- attention guidance
- feedback signals
- teaching session controls
- observation tools

It must not provide:
- automatic object labels
- pretrained object detection
- dictionary lookup
- text-based knowledge injection
- internet lookup

---

## 3. What the Caregiver Sees

The caregiver UI should show:

```
1. Live camera view
2. Live microphone/audio level
3. System attention overlay
4. Tracked object candidates
5. Current arousal/sleep state
6. Current teaching episode status
7. Recent feedback history
8. Current learned association candidates
```

### 3.1 Live Camera View

Displays the raw camera feed.

Overlay options:
- current frame
- object candidate boxes
- tracked object IDs
- attention target highlight
- confidence indicators

**Important:** Object labels are not shown unless they were learned by the system.

### 3.2 Audio Monitor

Displays:
- input volume
- detected speech-like rhythm
- current audio chunk status
- target sound capture status
- system output waveform when it babbles or imitates

Optional visualizations:
- waveform
- spectrogram
- target vs attempt similarity

### 3.3 System State Panel

Displays:

```
current_mode:             DEEP_SLEEP / LIGHT_SLEEP / WAKEFUL / FOCUSED / RECOVERY
arousal_level
sleep_pressure
fatigue_level
curiosity_drive
social_drive
stability_drive
current_development_stage
```

Purpose: the caregiver can understand whether the system is attentive, tired, overloaded, or ready to learn.

### 3.4 Attention Panel

Displays:

```
current_attention_target
attention_confidence
tracked_object_id
time_on_target
last_caregiver_pointer_event
```

This tells the caregiver what the system appears to be focusing on.

### 3.5 Association Panel

Displays candidate associations, not final truths.

Example:

```
Association Candidate:
  visual_target:    object_slot_003
  audio_pattern:    pattern_017
  binding_strength: 0.42
  exposures:        7
  last_feedback:    positive
```

The caregiver should see that the system is forming a possible association without treating it as confirmed knowledge.

---

## 4. Caregiver Controls

### 4.1 Point / Joint Attention Control

The caregiver can point to a region in the live camera feed.

Supported actions:
```
Click point
Draw bounding box
Select tracked object
Clear attention target
Hold attention target
```

These produce:
```
CaregiverPointerEvent
AttentionTargetEvent
ReferentCandidateEvent
```

This is the digital equivalent of pointing at an object.

### 4.2 Feedback Controls

The caregiver can provide simple feedback.

Buttons:
```
GOOD
BAD
YES
NO
AGAIN
STOP
REST
```

These do not inject meaning at first. They provide consistent reinforcement signals.

Event output:
```
CaregiverFeedbackEvent
```

Feedback should include:
- timestamp
- feedback type
- intensity
- current context
- current attention target
- recent system action

### 4.3 Teaching Episode Controls

A teaching episode is a structured interaction window.

Controls:
```
Start Teaching Episode
End Teaching Episode
Mark Target Sound
Repeat Target
Test Recall
Clear Episode
```

Episode types:
```
Object Attention Episode
Audio Imitation Episode
Cross-Modal Binding Episode
Free Interaction Episode
```

---

## 5. Teaching Episode Types

### 5.1 Object Attention Episode

**Purpose:** teach stable attention to a visual object.

Caregiver actions:
1. Start episode.
2. Point to object.
3. Keep object visible.
4. Move object slowly.
5. Provide GOOD when tracking persists.
6. Provide BAD/NO when attention drifts.

System objective: maintain object identity, track movement, reduce prediction error.

Success: object slot remains stable across time.

### 5.2 Audio Imitation Episode

**Purpose:** teach the system to imitate a sound.

Caregiver actions:
1. Start episode.
2. Press "Mark Target Sound."
3. Say or play a simple sound.
4. Let system attempt imitation.
5. Press GOOD when closer.
6. Press AGAIN for another attempt.
7. Press STOP to end.

System objective: encode target audio, generate motor output, compare self-output to target, reduce acoustic error.

Success: generated sound becomes closer to target over attempts.

### 5.3 Cross-Modal Binding Episode

**Purpose:** bind an attended visual target to a caregiver sound pattern.

Caregiver actions:
1. Start episode.
2. Point to object.
3. Say target sound repeatedly.
4. Provide GOOD when attention remains on target.
5. Repeat across multiple contexts.

System objective: bind visual object latent with audio pattern latent, strengthen association through repetition, use prediction improvement as reinforcement.

Success:
- object presence increases expectation of target sound
- target sound biases attention toward object

### 5.4 Free Interaction Episode

**Purpose:** allow less structured exploration.

Caregiver actions:
- interact naturally
- provide occasional feedback
- point when useful
- stop if overload occurs

System objective: learn interaction rhythms, detect social timing, explore sound and attention.

---

## 6. UI Layout

Recommended prototype layout:

```
┌────────────────────────────────────────────────────┐
│ Live Camera Feed                                   │
│ - object boxes                                     │
│ - attention highlight                              │
│ - caregiver pointer overlay                        │
├────────────────────────────────────────────────────┤
│ Audio Panel                                        │
│ [mic level] [waveform] [target/attempt similarity] │
├────────────────────────────────────────────────────┤
│ Teaching Controls                                  │
│ [Start] [End] [Mark Target Sound] [Repeat] [Test]  │
├────────────────────────────────────────────────────┤
│ Feedback Controls                                  │
│ [GOOD] [BAD] [YES] [NO] [AGAIN] [STOP] [REST]      │
├────────────────────────────────────────────────────┤
│ System State                                       │
│ mode / arousal / sleep / fatigue / stage / drives  │
├────────────────────────────────────────────────────┤
│ Associations                                       │
│ candidate bindings / confidence / exposures        │
└────────────────────────────────────────────────────┘
```

---

## 7. API Events

### 7.1 CaregiverPointerEvent

```
type:                CaregiverPointerEvent
timestamp:           float
mode:                POINT | BOX | OBJECT_SELECT | CLEAR
screen_coordinates:  optional [x, y]
box_coordinates:     optional [x1, y1, x2, y2]
selected_object_id:  optional string
confidence:          float
episode_id:          optional string
```

### 7.2 CaregiverFeedbackEvent

```
type:                    CaregiverFeedbackEvent
timestamp:               float
feedback_type:           GOOD | BAD | YES | NO | AGAIN | STOP | REST
intensity:               float [0.0, 1.0]
target_event_id:         optional string
current_attention_target: optional string
episode_id:              optional string
notes:                   optional string
```

### 7.3 TeachingEpisodeEvent

```
type:         TeachingEpisodeEvent
timestamp:    float
episode_id:   string
episode_type: OBJECT_ATTENTION | AUDIO_IMITATION | CROSS_MODAL_BINDING | FREE_INTERACTION
status:       STARTED | ENDED | PAUSED | CANCELLED
```

### 7.4 TargetAudioEvent

```
type:         TargetAudioEvent
timestamp:    float
episode_id:   string
sample_rate:  int
audio_window: float32 tensor [N]
duration_ms:  int
source:       CAREGIVER
```

### 7.5 TestRecallEvent

```
type:                    TestRecallEvent
timestamp:               float
episode_id:              string
test_type:               VISUAL_TO_AUDIO | AUDIO_TO_VISUAL
target_object_id:        optional string
target_audio_pattern_id: optional string
```

---

## 8. Caregiver Feedback Semantics

The system does not initially understand words like "good" or "bad." Feedback buttons provide reliable training signals.

| Button | Meaning |
|---|---|
| GOOD | reinforce recent behavior; strengthen current association; increase social reward |
| BAD | penalize recent behavior; weaken current association; trigger correction state |
| YES | confirm current response or attention target |
| NO | reject current response or attention target |
| AGAIN | repeat attempt; maintain episode context |
| STOP | end current action; suppress continuation |
| REST | reduce arousal; allow sleep/recovery mode |

---

## 9. Caregiver Audio Capture

The caregiver can mark a sound target.

Rules:
- target audio must be captured as raw audio
- no text transcript is attached
- no phonetic label is attached
- the target is treated as an acoustic pattern

Example: caregiver presses "Mark Target Sound" and says "aaa."

The system receives only:
- waveform
- timestamp
- episode context
- attention target if present

It does not receive:
- spelling
- transcript
- meaning

---

## 10. Joint Attention Rules

A valid joint attention event requires:

```
caregiver pointer active
tracked visual target present
caregiver audio or feedback within time window
system attention overlaps target
```

Recommended temporal window:
```
0.5 to 3 seconds
```

If multiple visual candidates exist, association confidence should remain low unless the caregiver pointer disambiguates.

---

## 11. Preventing Accidental Knowledge Injection

The caregiver UI must not use:

```
auto-labeling objects
speech-to-text transcripts
object detection model labels
pretrained classifier outputs
internet search
dictionary definitions
```

Allowed:

```
human pointing
human voice
human feedback
manual episode control
```

The system may learn from the caregiver, but the software must not secretly provide adult knowledge.

---

## 12. Logging

The interface should log:

```
episode start/end
pointer events
feedback events
target audio events
system attention state
candidate association changes
reward/penalty signals
```

Raw audio/video logging should be:
- disabled by default
- optional
- bounded
- explicitly configured

Preferred logging: latents, event summaries, timestamps, and association metrics.

---

## 13. First UI Milestones

**Milestone 1:** Live camera feed + click-to-point + attention event generation

Success:
- caregiver clicks an object
- system receives a CaregiverPointerEvent
- attention target updates
- object tracking module receives target context

**Milestone 2:** Audio imitation episode UI

Success:
- caregiver records target sound
- system attempts imitation
- caregiver provides GOOD/BAD feedback
- reinforcement module receives feedback event

**Milestone 3:** Cross-modal binding episode

Success:
- caregiver points to object
- caregiver says repeated sound
- system forms association candidate
- caregiver reinforces or rejects it

---

**Final rule: the caregiver interface structures experience. It must not preload knowledge.**
