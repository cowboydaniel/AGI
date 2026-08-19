"""
Live teaching session — caregiver console.

Boots the real runtime and puts the caregiver in the loop: a continuously
updating level meter shows what the microphone is receiving, every segmented
episode is announced as it closes, and every schema match or formation is
reported with its distance. Reinforcement is delivered by keypress, so the
caregiver reinforces the moment the sound happens rather than after the fact.

    g / SPACE   GOOD      approve what was just heard
    b           BAD       disapprove
    y / n       YES / NO  weaker approval / disapproval
    a           AGAIN     encourage repetition
    r           REST      neutral settle cue
    s           status    print memory contents so far
    q           quit      save and exit

Nothing here labels a sound. Keys deliver valence and intensity only; the
system receives reinforcement, never vocabulary (CAREGIVER_INTERFACE.md
section 11).

Usage:
    python tools/teach.py [seconds]
    python tools/teach.py 120 --device 23
"""

import asyncio
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

# Keep the runtime's own logging out of the caregiver's view; this console is
# the interface, not the log.
logging.basicConfig(level=logging.ERROR,
                    format="%(levelname)-7s %(name)s: %(message)s")

import arousal            # noqa: E402
import audio_motor        # noqa: E402
import bus                # noqa: E402
import caregiver          # noqa: E402
import clock              # noqa: E402
import homeostasis        # noqa: E402
import memory             # noqa: E402
import mic_input          # noqa: E402
import orienting          # noqa: E402
import predictor          # noqa: E402
import sandbox            # noqa: E402
import sensory_gate       # noqa: E402
import state_store        # noqa: E402
import value              # noqa: E402
from events import AudioEnergyEvent   # noqa: E402

try:
    import msvcrt         # Windows keyboard polling
except ImportError:
    msvcrt = None

DURATION = 120.0
DEVICE = None
for i, arg in enumerate(sys.argv[1:], start=1):
    if arg == "--device" and i + 1 < len(sys.argv):
        DEVICE = int(sys.argv[i + 1])
    elif arg.replace(".", "", 1).isdigit():
        DURATION = float(arg)

KEYS = {
    "g": "GOOD", " ": "GOOD", "b": "BAD", "y": "YES",
    "n": "NO", "a": "AGAIN", "r": "REST",
}

_recent_rms: list = []
_events_this_session: list = []
_running = True


def out(line: str = "") -> None:
    print(line, flush=True)


# ── bus subscribers ────────────────────────────────────────────────────────────

async def on_audio(e: AudioEnergyEvent) -> None:
    _recent_rms.append(e.rms)


async def on_episode(e) -> None:
    _events_this_session.append(e)
    out(f"\n  HEARD  episode #{e.episode_id}  "
        f"{e.duration_chunks} chunks (~{e.duration_chunks * 0.2:.1f}s)  "
        f"importance={e.importance:.2f}  {sorted(e.categories)}")


async def on_schema(e) -> None:
    if e.recognised:
        out(f"  ===>  RECOGNISED schema #{e.schema_id}   "
            f"instance {e.instances}   distance={e.distance:.4f}   "
            f"strength={e.strength:.2f}")
    else:
        near = f"nearest {e.distance:.4f} away" if e.distance >= 0 else "first ever"
        out(f"  ++++  NEW schema #{e.schema_id}   ({near})")
    out("        [g]ood [b]ad [y]es [n]o [a]gain [r]est  [s]tatus [q]uit")


async def on_consolidation(e) -> None:
    out(f"  ~~~~  consolidated: replayed {e.episodes_replayed}, "
        f"pruned {e.episodes_pruned} episodes / {e.schemas_pruned} schemas")


# ── console ────────────────────────────────────────────────────────────────────

def status() -> None:
    out("")
    out(f"  memory: {len(memory._episodes)} episodes, {len(memory._schemas)} schemas")
    for s in sorted(memory._schemas, key=lambda x: -x.instances):
        out(f"    schema #{s.schema_id}: {s.instances:3d} instances  "
            f"strength={s.strength:6.2f}")
    out(f"  predictor age: {predictor._chunks_trained} chunks  "
        f"error={predictor._ewa_error:.5f}")
    out("")


async def meter() -> None:
    """Continuous level display so the caregiver can see it listening."""
    global _running
    last = 0
    start = time.monotonic()
    while _running:
        await asyncio.sleep(0.4)
        window = _recent_rms[last:]
        last = len(_recent_rms)
        peak = max(window) if window else 0.0

        threshold = max(
            (state_store.get("mic_input.noise_floor", 0.001) or 0.001)
            * memory.EPISODE_FLOOR_MULT,
            memory.EPISODE_ABS_MIN_RMS,
        )
        width = 44
        filled = min(width, int((peak / 0.25) * width))
        mark = min(width - 1, int((threshold / 0.25) * width))
        bar = "".join(
            "#" if i < filled else ("|" if i == mark else "-")
            for i in range(width)
        )
        left = DURATION - (time.monotonic() - start)
        hot = "  <== HEARING YOU" if peak > threshold else ""
        print(f"\r  [{bar}] {peak:.3f}  {left:4.0f}s{hot}      ",
              end="", flush=True)


async def keyboard() -> None:
    """Poll for caregiver keypresses without blocking the event loop."""
    global _running
    if msvcrt is None:
        out("  (no keyboard polling on this platform — use the file channel: "
            f"echo GOOD >> {caregiver.FEEDBACK_PATH})")
        return
    while _running:
        await asyncio.sleep(0.05)
        while msvcrt.kbhit():
            try:
                ch = msvcrt.getwch().lower()
            except Exception:
                continue
            if ch == "q":
                _running = False
                return
            if ch == "s":
                status()
                continue
            token = KEYS.get(ch)
            if token:
                await caregiver.deliver(token)
                out(f"\n  <<<<  caregiver: {token}")


# ── main ───────────────────────────────────────────────────────────────────────

async def main() -> None:
    global _running

    out("=" * 68)
    out("  ACD TEACHING SESSION")
    out("=" * 68)

    state_store.init()
    if DEVICE is not None:
        state_store.set("mic_input.device_index", DEVICE)

    stage = state_store.get("development_stage", default=0)
    sandbox.init(stage=stage)
    bus.subscribe(sandbox.ActionRequestEvent, sandbox.handle_request)
    arousal.init()
    sensory_gate.init()
    orienting.init()
    homeostasis.init()
    predictor.init()
    value.init()
    memory.init()
    mic_input.init()
    audio_motor.init()
    caregiver.init()

    bus.subscribe(AudioEnergyEvent, on_audio)
    bus.subscribe(memory.EpisodeFormedEvent, on_episode)
    bus.subscribe(memory.SchemaEvent, on_schema)
    bus.subscribe(memory.ConsolidationEvent, on_consolidation)

    tasks = [
        asyncio.create_task(bus.run()),
        asyncio.create_task(clock.run()),
        asyncio.create_task(meter()),
        asyncio.create_task(keyboard()),
    ]
    await sensory_gate.apply_startup_gate()

    out(f"  carried in : {len(memory._episodes)} episodes, "
        f"{len(memory._schemas)} schemas")
    out(f"  predictor  : {predictor._chunks_trained} chunks of prior experience")
    out(f"  mic device : {mic_input._device_index}  @ {mic_input._device_rate} Hz")
    out(f"  match dist : {memory.SCHEMA_MATCH_DIST}   "
        f"episode range: {memory.EPISODE_MIN_CHUNKS}-{memory.EPISODE_MAX_CHUNKS} chunks")
    out("")
    out("  Say your word clearly, then PAUSE ~1s so the episode closes.")
    out("  Press g right after a good repetition. | marks the hearing threshold.")
    out("")

    start = time.monotonic()
    while _running and (time.monotonic() - start) < DURATION:
        await asyncio.sleep(0.2)
    _running = False

    for t in tasks:
        t.cancel()
        try:
            await t
        except asyncio.CancelledError:
            pass
    mic_input._close_stream()

    out("")
    out("=" * 68)
    out("  SESSION SUMMARY")
    out("=" * 68)
    out(f"  episodes this session : {len(_events_this_session)}")
    out(f"  episodes in memory    : {len(memory._episodes)}")
    out(f"  schemas               : {len(memory._schemas)}")
    for s in sorted(memory._schemas, key=lambda x: -x.instances):
        out(f"    schema #{s.schema_id}: {s.instances:3d} instances   "
            f"strength={s.strength:6.2f}")
    out(f"  caregiver feedback    : {caregiver._delivered} signals delivered")

    predictor.save_state()
    memory.save_state()
    audio_motor.save_state()
    state_store.close()
    out("  memory saved — it will be there next session.")


if __name__ == "__main__":
    asyncio.run(main())
