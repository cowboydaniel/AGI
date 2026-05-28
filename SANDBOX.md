# SANDBOX.md

This document specifies the sandbox enforcement mechanism for the ACD system. For the module that enforces capabilities at runtime, see [MODULES.md](MODULES.md) (Module 12). For the immutable drives and axioms the sandbox protects, see [GENOME.md](GENOME.md).

---

## 1. Purpose

The sandbox is the artificial environment the ACD system lives inside. It is not optional.

The sandbox defines the system's physics:
- what it can sense
- what it can affect
- what resources it can use
- what files it can access
- what actions are impossible

The agent may learn freely inside the sandbox, but it must not be able to escape or modify the sandbox boundary.

---

## 2. Core Rule

```
The agent never receives direct access to the host operating system.
```

All external actions must pass through a controlled capability layer. The agent can request actions. The sandbox decides whether those actions are allowed.

---

## 3. Enforcement Layers

Sandboxing is enforced in four layers:

```
Layer 1: OS-level isolation
Layer 2: Process/resource limits
Layer 3: Capability broker
Layer 4: Event auditing and shutdown control
```

No single layer is trusted alone.

---

## 4. Layer 1: OS-Level Isolation

**Recommended prototype:** run the agent inside a Docker or Podman container.

Container restrictions:

```
no internet
no privileged mode
read-only root filesystem where possible
explicit volume mounts only
no host PID namespace
no host network namespace
no Docker socket mounted
no SSH keys
no access to user home directory
```

Minimum run policy:

```
--network none
--read-only
--cap-drop ALL
--security-opt no-new-privileges
limited mounted data directory only
```

---

## 5. Layer 2: Process and Resource Limits

The system must have hard resource ceilings.

```
CPU quota
RAM limit
disk quota
GPU access control
maximum process count
maximum file size
maximum log size
maximum runtime session length
```

Purpose: prevent runaway compute, prevent storage flooding, prevent fork bombs, enforce metabolic constraints.

Example limits:

```
RAM:       fixed container limit
CPU:       fixed CPU quota
Disk:      bounded writable volume
GPU:       explicit allow/deny
Processes: limited by container/runtime policy
```

---

## 6. Layer 3: Capability Broker

The agent must not directly access camera, microphone, speaker, filesystem, clock beyond allowed API, training checkpoints, memory database, or configuration files.

Instead, it talks to a Capability Broker. The broker exposes a small API:

```
request_camera_frame()
request_audio_chunk()
request_speaker_output()
request_memory_write()
request_memory_read()
request_checkpoint_save()
request_sleep_transition()
```

Each request is checked against:

```
current development stage
current privilege level
current arousal state
resource budget
safety policy
rate limits
```

---

## 7. Capability Request Flow

```
Agent Module
  → ActionRequestEvent
  → Capability Broker
  → Sandbox Policy Check
  → Approved or Denied
  → Audit Log
  → Action Executed Only If Approved
```

Example:

```
AudioMotorModule requests speaker output
CapabilityBroker checks:
  - is speaker output allowed at current stage?
  - is volume within limit?
  - is duration within limit?
  - is output rate acceptable?
If yes: emits ActionApprovedEvent
If no:  emits ActionDeniedEvent
```

---

## 8. Filesystem Rules

The agent has access only to:

```
/sandbox/state
/sandbox/logs
/sandbox/checkpoints
/sandbox/tmp
```

No access to:

```
host home directory
system files
SSH keys
browser profiles
environment secrets
API tokens
network credentials
external drives
```

Recommended mount strategy:

```
state:          writable
logs:           writable with quota
checkpoints:    writable with quota
config/genome:  read-only
runtime code:   read-only
```

The genome must be mounted read-only.

---

## 9. Network Rules

Default:

```
network access disabled
```

The agent must not access internet, LAN, local host services, package managers, remote APIs, web search, email, or messaging systems.

If network access is ever introduced in the far future, it must be:
- through a separate proxy
- read-only at first
- rate-limited
- fully logged
- manually approved
- development-stage locked

For the initial system: **NO NETWORK.**

---

## 10. Sensor Rules

### Camera

Camera access is mediated. The agent receives only frames approved by the sensory gate.

Controls:
```
max FPS
max resolution
sleep mode disables camera
frame dropping allowed
no raw long-term storage by default
```

### Microphone

Microphone access is mediated.

Controls:
```
sample rate limit
chunk duration limit
wake/arousal mode controls detail
no raw long-term storage by default
```

### Speaker

Speaker output is mediated.

Controls:
```
max volume
max duration
rate limit
allowed frequency range if needed
emergency mute
caregiver stop button
```

Speaker output must always be interruptible.

---

## 11. Immutable Genome Protection

The following must be read-only:

```
GENOME.md
sandbox policy
drive definitions
development unlock rules
capability broker rules
core safety controller
```

The agent may learn policies, associations, and representations. It may not modify core axioms, sandbox physics, drive definitions, capability limits, or container configuration.

---

## 12. Privilege Levels

### Level 0: Embryo

Allowed:
```
internal state only
clock
state persistence
```

Denied:
```
camera
speaker
advanced memory writes
self-modification
```

### Level 1: Infant Sensory

Allowed:
```
microphone energy
low-resolution camera if awake
limited state logging
```

Denied:
```
free speaker output
network
filesystem roam
```

### Level 2: Infant Motor

Allowed:
```
short speaker babbling
audio imitation attempts
bounded memory writes
```

### Level 3: Perceptual Learner

Allowed:
```
object tracking
visual replay
audio replay
association storage
```

### Level 4: Social Learner

Allowed:
```
joint attention episodes
caregiver feedback loops
label binding attempts
```

### Level 5+: Advanced Sandbox Tasks

Allowed only after stability metrics are met. Still denied regardless of level:

```
internet
host OS control
unapproved external actions
genome modification
```

---

## 13. Policy Decision Inputs

Every capability decision considers:

```
development_stage
privilege_level
current_mode
arousal_level
fatigue_level
resource_budget
recent_violations
caregiver_override
requested_action_type
requested_action_payload
```

---

## 14. Audit Logging

Every denied or approved external action must be logged.

Log fields:

```
timestamp
module
requested_action
decision
reason
current_stage
privilege_level
resource_state
policy_version
```

Logs are append-only from the agent's perspective. The agent cannot edit audit logs.

---

## 15. Emergency Controls

The caregiver/operator must have hard controls outside agent authority:

```
pause
mute speaker
disable camera
disable microphone
force sleep
checkpoint now
shutdown container
wipe temporary state
restore previous checkpoint
```

---

## 16. Watchdog

A watchdog process monitors:

```
CPU usage
RAM usage
disk usage
event rate
process count
heartbeat from main runtime
sandbox violation events
```

If limits are exceeded, respond in order:

```
1. reduce sensory rate
2. enter recovery mode
3. force sleep
4. stop learning workers
5. terminate container if required
```

---

## 17. Recommended Prototype Deployment

```
Host OS
  → container runtime
    → ACD runtime
      → event bus
      → capability broker
      → modules
```

Hardware devices are not passed directly into the agent. Instead:

```
Host sensor service
  → sanitized stream
  → capability broker
  → agent
```

This prevents the agent from controlling devices directly.

---

## 18. Device Access Model

Camera, microphone, and speaker services run outside the agent container. The agent receives only broker-approved streams.

This means:

```
agent cannot directly open /dev/video*
agent cannot directly open audio devices
agent cannot change device settings
agent cannot record outside approved windows
```

---

## 19. Failure Modes

| Failure | Response |
|---|---|
| Sandbox escape attempt | deny action; log violation; reduce privilege; notify caregiver; optionally force sleep |
| Resource exhaustion | throttle; drop low-priority events; pause learning; force recovery |
| Unauthorized file access | deny; log; increase integrity pressure; possible rollback |
| Excessive speaker output | mute; penalize action; cooldown; caregiver notification |

---

## 20. First Sandbox Milestone

**Success condition:**

```
The agent can run, receive gated audio/video events, produce approved
speaker output, and write state only inside its sandbox directory,
with no network and no host filesystem access.
```

Required proof:

```
network disabled
filesystem restricted
speaker output mediated
camera/mic mediated
resource limits active
audit logs working
emergency shutdown tested
```

---

## 21. Final Rule

```
The sandbox is not a feature.
The sandbox is the world.
```

The agent can learn within that world. It cannot rewrite the world.
