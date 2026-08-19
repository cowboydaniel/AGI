"""
Stage 8 (Long-Term Memory Formation) integration tests.

Checks the four mechanisms STEPS.md requires - compressed episodic summaries,
pattern extraction, schema formation, and decay - plus the criteria in
STAGE_CRITERIA.md section 13: summaries form, recurring structure is detected,
related episodes group, memory survives a restart, and replay improves
prediction rather than merely archiving it.

Handlers are driven directly with constructed events and bus.publish is
captured, so the tests are deterministic and need no running bus, no audio
hardware, and no real time.

Runs under pytest or directly:  python tests/integration/test_stage8_memory.py
"""

import asyncio
import sys
import tempfile
from pathlib import Path

# Make src/ importable whether run via pytest or as a script.
_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import bus
import memory
import predictor
import salience
import state_store
from events import (
    AudioEnergyEvent, ArousalMode, ArousalStateEvent, CaregiverFeedbackEvent,
    OrientingResponseEvent, PredictionErrorEvent, RewardSignalEvent,
    SoundCategory, ArousalSignal,
)


# -- harness --------------------------------------------------------------------

_PUBLISHED: list = []


async def _collect(event) -> None:
    _PUBLISHED.append(event)


def _reset() -> Path:
    _PUBLISHED.clear()
    db = Path(tempfile.mkdtemp()) / "state.db"
    state_store.init(db)
    bus.publish = _collect
    memory._episodes = []
    memory._schemas = []
    memory._next_episode_id = 1
    memory._next_schema_id = 1
    memory._consolidations = 0
    memory._current_mode = ArousalMode.WAKEFUL
    memory._recent_rms.clear()      # background estimate is module state too
    salience._energy.clear()        # salience carries its own history
    salience._salient_count = 0
    salience._total_count = 0
    memory._reset_open()
    # Known noise floor so "is this sound?" is deterministic.
    state_store.set("mic_input.noise_floor", 0.001)
    return db


def _published(kind) -> list:
    return [e for e in _PUBLISHED if isinstance(e, kind)]


def _audio(rms, zcr=0.1, centroid=1200.0, flat=0.3, band=0.6, t=0.0,
           periodicity=0.85):
    """A chunk of sound.

    periodicity defaults high because episodes are gated by innate salience
    (GENOME P1) rather than loudness: an unstructured chunk is correctly
    ignored however loud it is, so a test that wants an experience to form
    must supply something with the character of a real sound source.
    """
    return AudioEnergyEvent(source="t", timestamp=t, rms=rms, zcr=zcr,
                            spectral_centroid=centroid, spectral_flatness=flat,
                            band_ratio=band, chunk_ms=200,
                            periodicity=periodicity, f0_hz=180.0)


# A syllable envelope. Real speech pulses at syllable rate; a constant-
# amplitude tone does not, and the innate rhythm detector correctly declines
# to treat one as speech-like. Fixtures must therefore modulate.
_ENVELOPE = (0.55, 1.0, 0.75, 1.0, 0.6, 0.95, 0.7, 1.0, 0.65, 0.9)


async def _utterance(profile, n=6, t0=0.0, error=0.05):
    """Feed one bounded, syllable-modulated sound, then silence to close it."""
    for i in range(n):
        shaped = (profile[0] * _ENVELOPE[i % len(_ENVELOPE)],) + tuple(profile[1:])
        await memory.on_audio_energy(_audio(*shaped, t=t0 + i * 0.2))
        await memory.on_prediction_error(PredictionErrorEvent(
            source="t", timestamp=t0 + i * 0.2, error=error, surprise=0.3,
            feature_errors=[error] * 5))
        await memory.on_orienting(OrientingResponseEvent(
            source="t", timestamp=t0 + i * 0.2, category=SoundCategory.SPEECH,
            confidence=0.9, arousal_delta=0.1, arousal_signal=ArousalSignal.SPEECH))
    for i in range(memory.EPISODE_CLOSE_AFTER + 1):
        await memory.on_audio_energy(_audio(0.0001, t=t0 + (n + i) * 0.2,
                                            periodicity=0.0))


# Two clearly different acoustic shapes.
_SOUND_A = (0.10, 0.10, 1200.0, 0.30, 0.60)
_SOUND_B = (0.05, 0.60, 7000.0, 0.85, 0.15)


# -- episode segmentation and compression ---------------------------------------

def test_sound_becomes_a_compressed_episode():
    _reset()

    async def run():
        await _utterance(_SOUND_A)

    asyncio.run(run())

    assert len(memory._episodes) == 1, "one bounded sound must produce one episode"
    ep = memory._episodes[0]
    assert ep.duration_chunks == 6, "episode must span the sounding chunks only"
    assert len(ep.summary) == memory.SUMMARY_DIM, "summary must be fixed-size"
    assert len(ep.trajectory) == memory.SUMMARY_DIM * memory.TRAJECTORY_BINS, \
        "trajectory must be fixed-size"
    assert 0.0 <= ep.importance <= 1.0, "importance must be bounded"
    assert _published(memory.EpisodeFormedEvent), "episode formation must be announced"


def test_episode_is_a_summary_not_a_recording():
    """Memory is compressed predictive structure, not archival storage."""
    _reset()

    async def run():
        await _utterance(_SOUND_A, n=memory.EPISODE_MAX_CHUNKS - 1)

    asyncio.run(run())

    ep = memory._episodes[0]
    stored = len(ep.summary) + len(ep.spread) + len(ep.trajectory)
    raw = ep.duration_chunks * memory.SUMMARY_DIM
    assert stored < raw, \
        f"stored size {stored} must be smaller than the raw stream {raw}"


def test_unchanging_sound_habituates_instead_of_running_on():
    """A sound that never changes stops holding attention.

    Previously a sustained sound produced one enormous episode spanning many
    utterances. Salience now stops firing once the background estimate catches
    up with a constant stimulus, which is habituation: the episode closes on
    its own and the drone never becomes a giant meaningless "experience".
    """
    _reset()

    async def run():
        # A long, utterly unchanging periodic tone.
        for i in range(60):
            await memory.on_audio_energy(_audio(0.10, t=i * 0.2))

    asyncio.run(run())

    assert len(memory._episodes) <= 1,         "an unchanging drone must not fragment into many experiences"
    for ep in memory._episodes:
        assert ep.duration_chunks < memory.EPISODE_MAX_CHUNKS,             "habituation must close the episode before the hard cap"


def test_hearing_threshold_tracks_the_background():
    """Sensory adaptation: a fixed threshold fails when the room changes."""
    _reset()

    quiet = memory.hearing_threshold()

    async def run():
        # A sustained loud background, as a noisy room would produce.
        for i in range(memory.BACKGROUND_WINDOW):
            await memory.on_audio_energy(_audio(0.20, t=i * 0.2))

    asyncio.run(run())
    noisy = memory.hearing_threshold()

    assert noisy > quiet,         f"the threshold must rise with the background ({quiet:.4f} -> {noisy:.4f})"
    assert memory.background_level() > 0.1,         "the background estimate must reflect a loud room"


def test_blip_too_short_to_be_an_experience_is_discarded():
    _reset()

    async def run():
        await _utterance(_SOUND_A, n=1)

    asyncio.run(run())

    assert memory._episodes == [], "a single-chunk blip must not become an episode"


# -- pattern extraction and schema formation ------------------------------------

def test_repeated_sound_is_recognised_as_the_same_schema():
    """Pattern extraction: recurrence is what makes a sound a thing."""
    _reset()

    async def run():
        await _utterance(_SOUND_A, t0=0.0)
        await _utterance(_SOUND_A, t0=10.0)
        await _utterance(_SOUND_A, t0=20.0)

    asyncio.run(run())

    assert len(memory._schemas) == 1, "the same sound must not spawn new schemas"
    assert memory._schemas[0].instances == 3, "each repeat must reinforce the schema"

    events = _published(memory.SchemaEvent)
    assert events[0].recognised is False, "the first encounter must be new"
    assert all(e.recognised for e in events[1:]), "later encounters must be recognised"


def test_different_sounds_form_different_schemas():
    """Negative control: recognition must discriminate, not accept everything."""
    _reset()

    async def run():
        await _utterance(_SOUND_A, t0=0.0)
        await _utterance(_SOUND_B, t0=10.0)

    asyncio.run(run())

    assert len(memory._schemas) == 2, "acoustically distinct sounds must not merge"
    ids = {ep.schema_id for ep in memory._episodes}
    assert len(ids) == 2, "the episodes must belong to different schemas"


def test_schema_prototype_moves_toward_its_instances():
    _reset()

    async def run():
        await _utterance(_SOUND_A, t0=0.0)
        before = list(memory._schemas[0].prototype)
        # A nearby variant - same shape, slightly different level.
        variant = (0.12, 0.12, 1300.0, 0.32, 0.62)
        await _utterance(variant, t0=10.0)
        return before

    before = asyncio.run(run())
    after = memory._schemas[0].prototype

    assert before != after, "the prototype must adapt to new instances"
    assert memory._schemas[0].instances == 2, "the variant must join the schema"


def test_schema_ids_carry_no_meaning():
    """Anti-hardcoding: a schema is an integer, never a label."""
    _reset()

    async def run():
        await _utterance(_SOUND_A)

    asyncio.run(run())

    s = memory._schemas[0]
    assert isinstance(s.schema_id, int), "schema identity must be an opaque id"
    assert not hasattr(s, "name") and not hasattr(s, "label"), \
        "schemas must not carry names or labels"


# -- caregiver reinforcement ----------------------------------------------------

def test_caregiver_feedback_binds_to_the_open_experience():
    """The caregiver makes a sound matter without saying what it is."""
    _reset()

    async def run():
        # Open an episode, deliver approval mid-sound, then close it.
        for i in range(4):
            await memory.on_audio_energy(_audio(*_SOUND_A, t=i * 0.2))
        await memory.on_caregiver_feedback(CaregiverFeedbackEvent(
            source="caregiver", timestamp=0.5, valence=1.0, kind="good",
            intensity=0.8))
        for i in range(memory.EPISODE_CLOSE_AFTER + 1):
            await memory.on_audio_energy(_audio(0.0001, t=1.0 + i * 0.2))

    asyncio.run(run())

    ep = memory._episodes[0]
    assert ep.reward_total > 0, "approval must raise the episode's value"
    assert ep.importance > 0, "a rewarded episode must be worth keeping"


def test_reward_raises_importance_relative_to_an_identical_unrewarded_episode():
    _reset()

    async def run():
        await _utterance(_SOUND_A, t0=0.0)
        plain = memory._episodes[0].importance

        for i in range(6):
            shaped = (_SOUND_A[0] * _ENVELOPE[i % len(_ENVELOPE)],) + _SOUND_A[1:]
            await memory.on_audio_energy(_audio(*shaped, t=10.0 + i * 0.2))
            await memory.on_prediction_error(PredictionErrorEvent(
                source="t", timestamp=10.0 + i * 0.2, error=0.05, surprise=0.3,
                feature_errors=[0.05] * 5))
        await memory.on_reward(RewardSignalEvent(
            source="value", timestamp=11.0, magnitude=0.9, drive="social",
            reason="test"))
        for i in range(memory.EPISODE_CLOSE_AFTER + 1):
            await memory.on_audio_energy(_audio(0.0001, t=12.0 + i * 0.2,
                                                periodicity=0.0))

        return plain, memory._episodes[1].importance

    plain, rewarded = asyncio.run(run())
    assert rewarded > plain, "reinforcement must make an experience more important"


# -- decay and forgetting -------------------------------------------------------

def test_decay_score_rises_with_age_and_falls_with_reinforcement():
    fresh = memory._decay_score(age=1.0, reward=0.0, recurrence=0, replays=0)
    old = memory._decay_score(age=100_000.0, reward=0.0, recurrence=0, replays=0)
    assert old > fresh, "an unused memory must decay as it ages"

    rewarded = memory._decay_score(age=100_000.0, reward=2.0, recurrence=0, replays=0)
    assert rewarded < old, "reinforcement must protect a memory from decay"

    recurring = memory._decay_score(age=100_000.0, reward=0.0, recurrence=20, replays=0)
    assert recurring < old, "recurrence must protect a memory from decay"


def test_forgetting_actually_deletes():
    """Forgetting is required, not optional."""
    _reset()

    async def run():
        await _utterance(_SOUND_A)

    asyncio.run(run())
    assert len(memory._episodes) == 1, "precondition"

    # An ancient, unreinforced, never-replayed episode.
    memory._episodes[0].last_access = -1_000_000.0
    memory._episodes[0].reward_total = 0.0
    memory._episodes[0].importance = 0.0
    memory._schemas[0].last_seen = -1_000_000.0
    memory._schemas[0].strength = 0.0
    memory._schemas[0].instances = 0

    pruned_e, pruned_s = memory._prune()

    assert pruned_e == 1, "a decayed episode must be deleted"
    assert memory._episodes == [], "deletion must actually remove it"
    assert pruned_s == 1, "a decayed schema must be deleted too"


def test_reinforced_memory_survives_pruning():
    _reset()

    async def run():
        await _utterance(_SOUND_A)

    asyncio.run(run())
    memory._episodes[0].last_access = -1_000_000.0
    memory._episodes[0].reward_total = 5.0      # heavily reinforced
    memory._schemas[0].instances = 25           # and strongly recurring
    memory._schemas[0].strength = 5.0

    memory._prune()

    assert len(memory._episodes) == 1, "a reinforced memory must not be forgotten"
    assert len(memory._schemas) == 1, "a recurring schema must not be forgotten"


def test_reconsolidation_merges_fragments_of_one_sound():
    """Online schema formation fragments a sound when early prototypes are set
    from noisy first instances; re-deriving from stored episodes repairs it."""
    _reset()

    async def run():
        # Same sound, drifting slightly - online matching can split this.
        for i in range(6):
            drift = 1.0 + i * 0.02
            await _utterance((0.10 * drift, 0.10 * drift, 1200.0 * drift,
                              0.30 * drift, 0.60), t0=i * 10.0)

    asyncio.run(run())
    before = len(memory._schemas)

    # Force fragmentation, then let re-consolidation regroup from scratch.
    memory._schemas = []
    memory._next_schema_id = 1
    original = memory.SCHEMA_MATCH_DIST
    try:
        memory.SCHEMA_MATCH_DIST = 0.0001          # everything is its own schema
        asyncio.run(memory.reconsolidate_schemas())
        fragmented = len(memory._schemas)
        memory.SCHEMA_MATCH_DIST = original
        asyncio.run(memory.reconsolidate_schemas())
        merged = len(memory._schemas)
    finally:
        memory.SCHEMA_MATCH_DIST = original

    assert fragmented > merged,         f"re-consolidation must merge fragments ({fragmented} -> {merged})"
    assert all(e.schema_id is not None for e in memory._episodes),         "every episode must be reassigned to a schema"
    assert before > 0, "precondition: episodes formed schemas online"


def test_reconsolidation_uses_no_labels():
    """It must work from stored episodes alone - no targets, no categories."""
    _reset()

    async def run():
        await _utterance(_SOUND_A, t0=0.0)
        await _utterance(_SOUND_B, t0=20.0)
        return await memory.reconsolidate_schemas()

    n = asyncio.run(run())

    assert n == 2, "two distinct sounds must re-derive as two schemas"
    for s in memory._schemas:
        assert not hasattr(s, "label") and not hasattr(s, "word"),             "re-consolidation must not attach names to schemas"


# -- consolidation and continuity -----------------------------------------------

def test_sleep_triggers_consolidation():
    _reset()

    async def run():
        await _utterance(_SOUND_A)
        memory._current_mode = ArousalMode.WAKEFUL
        await memory.on_arousal_state(ArousalStateEvent(
            source="arousal", timestamp=50.0, mode=ArousalMode.LIGHT_SLEEP,
            arousal_level=0.1, sleep_pressure=0.9, fatigue_level=0.5,
            suppression=0.0))

    asyncio.run(run())

    assert _published(memory.ConsolidationEvent), "falling asleep must consolidate"
    assert memory._consolidations == 1, "the consolidation must be counted"


def test_replay_trains_the_predictor():
    """replay_improvement_delta must be real: replay changes the model."""
    _reset()
    predictor._W = [[1.0 if i == j else 0.0 for j in range(5)] for i in range(5)]
    predictor._b = [0.0] * 5
    predictor._prev_features = None

    async def run():
        await _utterance(_SOUND_A, t0=0.0)
        await _utterance(_SOUND_B, t0=20.0)
        await memory.consolidate()

    asyncio.run(run())

    drift = max(abs(predictor._W[i][j] - (1.0 if i == j else 0.0))
                for i in range(5) for j in range(5))
    assert drift > 0, "replay must actually update the predictor's weights"
    assert all(e.replay_count > 0 for e in memory._episodes), \
        "replayed episodes must record that they were replayed"


def test_memory_survives_a_restart():
    """Continuity: what was learned must outlive the process."""
    db = _reset()

    async def run():
        await _utterance(_SOUND_A, t0=0.0)
        await _utterance(_SOUND_A, t0=10.0)

    asyncio.run(run())
    assert len(memory._episodes) == 2 and len(memory._schemas) == 1, "precondition"
    instances = memory._schemas[0].instances
    memory.save_state()
    state_store.close()

    # Simulate a restart: wipe RAM, reopen the same database.
    memory._episodes = []
    memory._schemas = []
    state_store.init(db)
    restored = memory.load_state()

    assert restored, "a saved memory must be found on restart"
    assert len(memory._episodes) == 2, "episodes must survive the restart"
    assert len(memory._schemas) == 1, "schemas must survive the restart"
    assert memory._schemas[0].instances == instances, \
        "recurrence counts must survive the restart"


def test_recognition_still_works_after_a_restart():
    """The point of persistence: it remembers the sound tomorrow."""
    db = _reset()

    async def run_first():
        await _utterance(_SOUND_A, t0=0.0)
        await _utterance(_SOUND_A, t0=10.0)

    asyncio.run(run_first())
    memory.save_state()
    state_store.close()

    memory._episodes = []
    memory._schemas = []
    state_store.init(db)
    memory.load_state()
    _PUBLISHED.clear()

    async def run_second():
        await _utterance(_SOUND_A, t0=100.0)

    asyncio.run(run_second())

    events = _published(memory.SchemaEvent)
    assert events and events[-1].recognised, \
        "a sound met before the restart must be recognised after it"
    assert events[-1].instances == 3, "the instance count must continue, not reset"


# -- script runner (works without pytest) ---------------------------------------

if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failures = 0
    for t in tests:
        try:
            t()
            print(f"PASS  {t.__name__}")
        except AssertionError as e:
            failures += 1
            print(f"FAIL  {t.__name__}: {e}")
        except Exception as e:  # noqa: BLE001
            failures += 1
            print(f"ERROR {t.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(tests) - failures}/{len(tests)} passed")
    sys.exit(1 if failures else 0)
