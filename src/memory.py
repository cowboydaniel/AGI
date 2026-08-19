"""
Long-Term Memory Formation — Stage 8.

Goal (STEPS.md): structural consolidation. Memory begins shaping behaviour.

This module turns a continuous sensory stream into durable structure through
four mechanisms, in order:

  1. Episode segmentation  — the stream is cut into bounded experiences.
     An episode opens when sound rises above the calibrated noise floor and
     closes after sustained silence. Nothing labels the episode; it is simply
     "a thing that happened".

  2. Compressed summaries  — an episode is never stored raw. It is reduced to
     a fixed-size sketch: per-feature mean and spread, a coarse trajectory,
     duration, the category sequence, prediction-error statistics, and the
     reward accumulated while it ran (MEMORY_ARCHITECTURE.md section 5).
     Memory is compressed predictive structure, not an archive.

  3. Pattern extraction and schema formation — each new summary is compared to
     existing schemas by distance in summary space. A close match reinforces
     that schema and pulls its prototype toward the new instance; no match
     creates a new schema. A schema is therefore a sound-shape the system has
     met more than once. This is the mechanism by which a repeated sound
     becomes a *thing* rather than a passing sensation — and it is only a
     mechanism: nothing here knows what any schema means.

  4. Decay and forgetting  — every schema and episode carries a decay score
     driven by age, reinforcement, recurrence and replay
     (MEMORY_ARCHITECTURE.md section 10). Structures that stop earning their
     place are deleted. Forgetting is required, not optional.

During sleep the module replays high-importance episodes back through the
predictor, which is what makes consolidation improve prediction rather than
merely archive it, and checkpoints the learned model.

Anti-hardcoding note: no vocabulary, no categories, and no target patterns are
supplied. Schemas are discovered by recurrence alone, and a schema's identity
is an arbitrary integer id, never a name.
"""

import logging
import math
import time
from dataclasses import dataclass, field, asdict

import bus
import clock
import predictor
import state_store
from events import (
    AudioEnergyEvent, ArousalMode, ArousalStateEvent, OrientingResponseEvent,
    PredictionErrorEvent, RewardSignalEvent, PenaltySignalEvent,
    SoundCategory, CaregiverFeedbackEvent,
)

logger = logging.getLogger(__name__)

# ── tuning ─────────────────────────────────────────────────────────────────────

SUMMARY_DIM         = 5      # the five acoustic features
TRAJECTORY_BINS     = 3      # coarse start/middle/end shape per feature

EPISODE_MIN_CHUNKS  = 2      # shorter than this is a blip, not an experience
EPISODE_MAX_CHUNKS  = 25     # ~5 s at a 200 ms window: an utterance, not an hour
EPISODE_CLOSE_AFTER = 3      # consecutive silent chunks that end an episode

# Hearing threshold. A perceptual sensitivity (genome-level), not knowledge:
# it says how loud something must be to count as an event, never what the
# event is. Set well above the measured noise floor, because room hiss and
# fan noise otherwise segment into endless empty "experiences".
EPISODE_FLOOR_MULT  = 8.0    # multiple of the calibrated noise floor
EPISODE_ABS_MIN_RMS = 0.015  # absolute backstop if the floor calibrates low
EPISODE_PEAK_MULT   = 2.5    # an episode's loudest chunk must clear the
                             # hearing threshold by this much to be kept

SCHEMA_MATCH_DIST   = 0.06   # match-space distance below which two episodes
                             # are treated as instances of the same shape.
                             # Too loose and every sound collapses into one
                             # schema; too tight and one sound fragments into
                             # many. Over-discrimination is the safer error.
SCHEMA_LEARN_RATE   = 0.25   # how far a prototype moves toward a new instance

MAX_EPISODES        = 400    # hard ceiling; decay prunes below this
MAX_SCHEMAS         = 120

# Decay weights (MEMORY_ARCHITECTURE.md section 10.4)
DECAY_AGE_W         = 0.35
DECAY_REWARD_W      = 0.60
DECAY_RECUR_W       = 0.45
DECAY_REPLAY_W      = 0.20
DECAY_DELETE_ABOVE  = 0.80   # decay score at which a structure is dropped

REPLAY_PER_CYCLE    = 12     # episodes replayed per sleep consolidation


# ── events ─────────────────────────────────────────────────────────────────────

@dataclass
class EpisodeFormedEvent(bus.Event):
    """A bounded experience was segmented and compressed."""
    episode_id:      int
    duration_chunks: int
    mean_error:      float
    reward_total:    float
    importance:      float
    categories:      list


@dataclass
class SchemaEvent(bus.Event):
    """A schema was created, or an existing one was recognised again.

    `recognised` False = this shape is new; True = the system has met it
    before. Repeated recognition of the same schema_id is the raw material
    for every later notion of "the same sound again".
    """
    schema_id:   int
    recognised:  bool
    instances:   int
    distance:    float
    strength:    float


@dataclass
class ConsolidationEvent(bus.Event):
    """Emitted after a sleep consolidation pass."""
    episodes_replayed: int
    episodes_pruned:   int
    schemas_pruned:    int
    error_before:      float
    error_after:       float
    improvement:       float


# ── records ────────────────────────────────────────────────────────────────────

@dataclass
class Episode:
    episode_id:      int
    t_start:         float
    t_end:           float
    duration_chunks: int
    summary:         list            # SUMMARY_DIM means
    spread:          list            # SUMMARY_DIM standard deviations
    trajectory:      list            # SUMMARY_DIM * TRAJECTORY_BINS
    categories:      list            # category sequence, as strings
    mean_error:      float
    error_delta:     float
    reward_total:    float
    importance:      float
    schema_id:       int | None = None
    replay_count:    int = 0
    last_access:     float = 0.0


@dataclass
class Schema:
    schema_id:    int
    prototype:    list               # running mean of member summaries
    instances:    int = 1
    strength:     float = 0.0        # accumulated reinforcement
    first_seen:   float = 0.0
    last_seen:    float = 0.0
    replay_count: int = 0


# ── state ──────────────────────────────────────────────────────────────────────

_episodes: list = []
_schemas:  list = []
_next_episode_id: int = 1
_next_schema_id:  int = 1

# Open episode accumulator (working memory — RAM only, never persisted)
_open_features:   list = []
_open_categories: list = []
_open_errors:     list = []
_open_reward:     float = 0.0
_open_start:      float = 0.0
_open_peak:       float = 0.0
_silent_run:      int = 0

_current_mode: ArousalMode = ArousalMode.LIGHT_SLEEP
_last_reward:  float = 0.0
_consolidations: int = 0


# ── helpers ────────────────────────────────────────────────────────────────────

def _encode(event: AudioEnergyEvent) -> list:
    """Same feature encoding the predictor uses, so both share a space."""
    return [
        event.rms,
        event.zcr,
        min(event.spectral_centroid / 16000.0, 1.0),
        event.spectral_flatness,
        event.band_ratio,
    ]


def _mean(xs: list) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def _stdev(xs: list) -> float:
    if len(xs) < 2:
        return 0.0
    m = _mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / len(xs))


def _distance(a: list, b: list) -> float:
    """Euclidean distance in summary space, normalised by dimension."""
    if not a or not b or len(a) != len(b):
        return float("inf")
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)) / len(a))


def _trajectory(frames: list) -> list:
    """Coarse shape: mean of each feature over TRAJECTORY_BINS time slices.

    This is what lets two utterances of the same rhythm match even when their
    absolute loudness differs — the shape survives, the level does not.
    """
    if not frames:
        return [0.0] * (SUMMARY_DIM * TRAJECTORY_BINS)
    n = len(frames)
    out = []
    for b in range(TRAJECTORY_BINS):
        lo = (n * b) // TRAJECTORY_BINS
        hi = max(lo + 1, (n * (b + 1)) // TRAJECTORY_BINS)
        chunk = frames[lo:hi]
        for d in range(SUMMARY_DIM):
            out.append(_mean([f[d] for f in chunk]))
    return out


def _importance(mean_error: float, error_delta: float, reward: float,
                duration: int) -> float:
    """How much this episode deserves to be kept.

    Surprising (high error), improving (negative delta), rewarded, and
    substantial episodes matter more. Bounded to [0,1].
    """
    surprise = min(1.0, mean_error * 4.0)
    progress = max(0.0, -error_delta * 8.0)
    value    = max(0.0, min(1.0, abs(reward)))
    length   = min(1.0, duration / 30.0)
    raw = 0.40 * surprise + 0.20 * progress + 0.30 * value + 0.10 * length
    return max(0.0, min(1.0, raw))


def _decay_score(age: float, reward: float, recurrence: int,
                 replays: int) -> float:
    """MEMORY_ARCHITECTURE.md section 10.4, as a logistic.

    High = forget me. Age pushes up; reinforcement, recurrence and replay
    push down. A structure that keeps proving useful never decays out.
    """
    z = (DECAY_AGE_W * math.log1p(max(0.0, age) / 60.0)
         - DECAY_REWARD_W * reward
         - DECAY_RECUR_W * math.log1p(max(0, recurrence))
         - DECAY_REPLAY_W * math.log1p(max(0, replays)))
    return 1.0 / (1.0 + math.exp(-z))


# ── schema formation ───────────────────────────────────────────────────────────

def _match_vector(ep: "Episode") -> list:
    """The vector two episodes are compared on.

    Summary alone is a bag of averages: a short word and a long hum of the
    same loudness and brightness look identical. Appending the trajectory
    makes temporal shape part of identity, which is what distinguishes one
    utterance from another.
    """
    return list(ep.summary) + list(ep.trajectory)


def _match_schema(vector: list) -> tuple:
    """Nearest existing schema and its distance."""
    best, best_d = None, float("inf")
    for s in _schemas:
        if len(s.prototype) != len(vector):
            continue          # a schema from an older match space — ignore it
        d = _distance(vector, s.prototype)
        if d < best_d:
            best, best_d = s, d
    return best, best_d


async def _assign_schema(ep: Episode, now: float) -> None:
    """Attach the episode to a schema, creating one if this shape is new.

    This is the whole of "the system recognised something". Recognition here
    means only: this sensory shape is close to one I have stored. No meaning,
    no name, no label.
    """
    global _next_schema_id

    vector = _match_vector(ep)
    match, dist = _match_schema(vector)

    if match is not None and dist <= SCHEMA_MATCH_DIST:
        # Known shape — pull the prototype toward this instance and reinforce.
        match.prototype = [
            p + SCHEMA_LEARN_RATE * (v - p)
            for p, v in zip(match.prototype, vector)
        ]
        match.instances += 1
        match.strength += max(0.0, ep.reward_total) + 0.1
        match.last_seen = now
        ep.schema_id = match.schema_id
        logger.info(
            "memory: RECOGNISED schema #%d (instance %d, dist=%.3f, strength=%.2f)",
            match.schema_id, match.instances, dist, match.strength,
        )
        await bus.publish(SchemaEvent(
            source="memory", timestamp=now, schema_id=match.schema_id,
            recognised=True, instances=match.instances, distance=dist,
            strength=match.strength,
        ))
        return

    schema = Schema(
        schema_id=_next_schema_id,
        prototype=list(vector),
        instances=1,
        strength=max(0.0, ep.reward_total),
        first_seen=now,
        last_seen=now,
    )
    _next_schema_id += 1
    _schemas.append(schema)
    ep.schema_id = schema.schema_id
    logger.info("memory: NEW schema #%d formed (nearest was %.3f away)",
                schema.schema_id, dist if dist != float("inf") else -1.0)
    await bus.publish(SchemaEvent(
        source="memory", timestamp=now, schema_id=schema.schema_id,
        recognised=False, instances=1,
        distance=dist if dist != float("inf") else -1.0, strength=schema.strength,
    ))


# ── episode segmentation ───────────────────────────────────────────────────────

def _reset_open() -> None:
    global _open_features, _open_categories, _open_errors, _open_reward
    global _open_start, _open_peak, _silent_run
    _open_features = []
    _open_categories = []
    _open_errors = []
    _open_reward = 0.0
    _open_start = 0.0
    _open_peak = 0.0
    _silent_run = 0


async def _close_episode(now: float) -> None:
    """Compress the open experience into a durable summary and store it."""
    global _next_episode_id

    frames = _open_features
    if len(frames) < EPISODE_MIN_CHUNKS:
        _reset_open()
        return

    # A sound that only grazed the hearing threshold is a blip in the room,
    # not an experience worth remembering. Without this, near-threshold noise
    # forms episodes that then match into schemas and dilute their prototypes.
    floor = state_store.get("mic_input.noise_floor", 0.001) or 0.001
    threshold = max(floor * EPISODE_FLOOR_MULT, EPISODE_ABS_MIN_RMS)
    if _open_peak < threshold * EPISODE_PEAK_MULT:
        logger.debug("memory: discarding marginal episode (peak=%.4f)", _open_peak)
        _reset_open()
        return

    summary = [_mean([f[d] for f in frames]) for d in range(SUMMARY_DIM)]
    spread  = [_stdev([f[d] for f in frames]) for d in range(SUMMARY_DIM)]

    errors = _open_errors or [0.0]
    half = max(1, len(errors) // 2)
    error_delta = _mean(errors[half:]) - _mean(errors[:half])

    ep = Episode(
        episode_id=_next_episode_id,
        t_start=_open_start,
        t_end=now,
        duration_chunks=len(frames),
        summary=summary,
        spread=spread,
        trajectory=_trajectory(frames),
        categories=list(_open_categories),
        mean_error=_mean(errors),
        error_delta=error_delta,
        reward_total=_open_reward,
        importance=_importance(_mean(errors), error_delta, _open_reward, len(frames)),
        last_access=now,
    )
    _next_episode_id += 1
    _episodes.append(ep)

    logger.info(
        "memory: episode #%d closed — %d chunks  err=%.4f  reward=%+.3f  importance=%.2f",
        ep.episode_id, ep.duration_chunks, ep.mean_error, ep.reward_total, ep.importance,
    )

    await _assign_schema(ep, now)

    await bus.publish(EpisodeFormedEvent(
        source="memory", timestamp=now, episode_id=ep.episode_id,
        duration_chunks=ep.duration_chunks, mean_error=ep.mean_error,
        reward_total=ep.reward_total, importance=ep.importance,
        categories=list(set(ep.categories)),
    ))

    state_store.set("memory.episodic_entry_count", len(_episodes))
    _reset_open()


# ── consolidation (sleep) ──────────────────────────────────────────────────────

def _prune() -> tuple:
    """Forget what has stopped earning its place. Returns (episodes, schemas)."""
    now = clock.elapsed()

    kept_e = []
    for ep in _episodes:
        recurrence = 0
        if ep.schema_id is not None:
            for s in _schemas:
                if s.schema_id == ep.schema_id:
                    recurrence = s.instances
                    break
        d = _decay_score(now - ep.last_access, ep.reward_total + ep.importance,
                         recurrence, ep.replay_count)
        if d < DECAY_DELETE_ABOVE:
            kept_e.append(ep)

    # Hard ceiling: keep the most important if still over budget.
    if len(kept_e) > MAX_EPISODES:
        kept_e.sort(key=lambda e: e.importance, reverse=True)
        kept_e = kept_e[:MAX_EPISODES]

    kept_s = []
    for s in _schemas:
        d = _decay_score(now - s.last_seen, s.strength, s.instances, s.replay_count)
        # A schema seen only once and long unreinforced is noise, not structure.
        if d < DECAY_DELETE_ABOVE:
            kept_s.append(s)
    if len(kept_s) > MAX_SCHEMAS:
        kept_s.sort(key=lambda s: (s.instances, s.strength), reverse=True)
        kept_s = kept_s[:MAX_SCHEMAS]

    pruned_e = len(_episodes) - len(kept_e)
    pruned_s = len(_schemas) - len(kept_s)
    _episodes[:] = kept_e
    _schemas[:] = kept_s
    return pruned_e, pruned_s


async def consolidate() -> None:
    """Sleep-time replay: re-train the predictor on remembered experience.

    Replay is what makes memory improve prediction instead of merely storing
    it (MEMORY_ARCHITECTURE.md section 11). Episodes are replayed most-
    important first, and the resulting change in model error is measured, so
    replay_improvement_delta is a real number rather than an assertion.
    """
    global _consolidations

    now = clock.elapsed()
    if not _episodes:
        logger.debug("memory: consolidation skipped — nothing remembered yet")
        return

    error_before = predictor._ewa_error

    ranked = sorted(_episodes, key=lambda e: e.importance, reverse=True)
    replayed = 0
    for ep in ranked[:REPLAY_PER_CYCLE]:
        # Replay the episode's trajectory as a short sequence, so the
        # predictor re-experiences its temporal shape, not just its mean.
        traj = ep.trajectory
        for b in range(TRAJECTORY_BINS):
            frame = traj[b * SUMMARY_DIM:(b + 1) * SUMMARY_DIM]
            if len(frame) != SUMMARY_DIM:
                continue
            if predictor._prev_features is not None:
                predictor._update(predictor._prev_features, frame)
            predictor._prev_features = frame
        ep.replay_count += 1
        ep.last_access = now
        replayed += 1

        if ep.schema_id is not None:
            for s in _schemas:
                if s.schema_id == ep.schema_id:
                    s.replay_count += 1
                    break

    error_after = predictor._ewa_error
    pruned_e, pruned_s = _prune()
    _consolidations += 1

    predictor.save_state()
    save_state()

    logger.info(
        "memory: consolidation #%d — replayed=%d  pruned=%d episodes/%d schemas  "
        "episodes=%d  schemas=%d",
        _consolidations, replayed, pruned_e, pruned_s, len(_episodes), len(_schemas),
    )

    await bus.publish(ConsolidationEvent(
        source="memory", timestamp=now, episodes_replayed=replayed,
        episodes_pruned=pruned_e, schemas_pruned=pruned_s,
        error_before=error_before, error_after=error_after,
        improvement=error_before - error_after,
    ))


# ── handlers ───────────────────────────────────────────────────────────────────

async def on_audio_energy(event: AudioEnergyEvent) -> None:
    global _open_start, _silent_run, _open_peak

    features = _encode(event)
    now = event.timestamp

    # Hearing threshold: loud enough to be an event at all. Anything quieter
    # is treated as silence and closes whatever episode is open.
    floor = state_store.get("mic_input.noise_floor", 0.001) or 0.001
    threshold = max(floor * EPISODE_FLOOR_MULT, EPISODE_ABS_MIN_RMS)
    is_sound = event.rms > threshold

    if is_sound:
        if not _open_features:
            _open_start = now
        _open_features.append(features)
        _open_peak = max(_open_peak, event.rms)
        _silent_run = 0
        if len(_open_features) >= EPISODE_MAX_CHUNKS:
            await _close_episode(now)
    elif _open_features:
        _silent_run += 1
        if _silent_run >= EPISODE_CLOSE_AFTER:
            await _close_episode(now)


async def on_prediction_error(event: PredictionErrorEvent) -> None:
    if _open_features:
        _open_errors.append(event.error)


async def on_orienting(event: OrientingResponseEvent) -> None:
    if _open_features:
        _open_categories.append(event.category.value)


async def on_reward(event: RewardSignalEvent) -> None:
    global _open_reward
    if _open_features:
        _open_reward += event.magnitude


async def on_penalty(event: PenaltySignalEvent) -> None:
    global _open_reward
    if _open_features:
        _open_reward -= event.magnitude


async def on_caregiver_feedback(event: CaregiverFeedbackEvent) -> None:
    """Caregiver reinforcement binds to whatever experience is open.

    This is how a caregiver makes one sound matter more than another without
    ever telling the system what the sound is.
    """
    global _open_reward
    if _open_features:
        _open_reward += event.valence * event.intensity
    else:
        # Feedback just after an episode closed still belongs to it.
        if _episodes:
            ep = _episodes[-1]
            ep.reward_total += event.valence * event.intensity
            ep.importance = _importance(ep.mean_error, ep.error_delta,
                                        ep.reward_total, ep.duration_chunks)
            for s in _schemas:
                if s.schema_id == ep.schema_id:
                    s.strength += event.valence * event.intensity
                    break


async def on_arousal_state(event: ArousalStateEvent) -> None:
    global _current_mode
    was_awake = _current_mode in (ArousalMode.WAKEFUL, ArousalMode.FOCUSED)
    _current_mode = event.mode
    now_asleep = event.mode in (ArousalMode.DEEP_SLEEP, ArousalMode.LIGHT_SLEEP,
                                ArousalMode.RECOVERY)
    # Falling asleep triggers consolidation — the biological arrangement.
    if was_awake and now_asleep:
        if _open_features:
            await _close_episode(event.timestamp)
        await consolidate()


# ── persistence ────────────────────────────────────────────────────────────────

def save_state() -> None:
    try:
        state_store.set("memory.episodes", [asdict(e) for e in _episodes])
        state_store.set("memory.schemas", [asdict(s) for s in _schemas])
        state_store.set("memory.next_episode_id", _next_episode_id)
        state_store.set("memory.next_schema_id", _next_schema_id)
        state_store.set("memory.episodic_entry_count", len(_episodes))
        logger.info("memory: saved %d episodes, %d schemas",
                    len(_episodes), len(_schemas))
    except Exception as e:
        logger.warning("memory: save failed (%s)", e)


def load_state() -> bool:
    global _episodes, _schemas, _next_episode_id, _next_schema_id
    try:
        eps = state_store.get("memory.episodes", None)
        scs = state_store.get("memory.schemas", None)
        if eps is None and scs is None:
            return False
        _episodes = [Episode(**e) for e in (eps or [])]
        _schemas = [Schema(**s) for s in (scs or [])]
        _next_episode_id = int(state_store.get("memory.next_episode_id", len(_episodes) + 1))
        _next_schema_id = int(state_store.get("memory.next_schema_id", len(_schemas) + 1))
        logger.info("memory: restored %d episodes, %d schemas",
                    len(_episodes), len(_schemas))
        return True
    except Exception as e:
        logger.warning("memory: load failed (%s) — starting fresh", e)
        _episodes, _schemas = [], []
        return False


def init() -> None:
    bus.subscribe(AudioEnergyEvent, on_audio_energy)
    bus.subscribe(PredictionErrorEvent, on_prediction_error)
    bus.subscribe(OrientingResponseEvent, on_orienting)
    bus.subscribe(RewardSignalEvent, on_reward)
    bus.subscribe(PenaltySignalEvent, on_penalty)
    bus.subscribe(CaregiverFeedbackEvent, on_caregiver_feedback)
    bus.subscribe(ArousalStateEvent, on_arousal_state)
    _reset_open()
    restored = load_state()
    logger.info(
        "memory (Stage 8) initialized — %s  match_dist=%.2f  decay_delete>%.2f",
        f"resumed {len(_episodes)} episodes / {len(_schemas)} schemas"
        if restored else "fresh memory",
        SCHEMA_MATCH_DIST, DECAY_DELETE_ABOVE,
    )
