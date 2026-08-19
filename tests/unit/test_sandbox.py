"""
Unit tests for the Stage 0 capability manager (src/sandbox.py).

Containment is principle 5 and non-negotiable, so these tests pin both halves
of the boundary: capabilities unlock cumulatively as the system develops, and
the forbidden set (network, genome modification, sandbox modification) is
never grantable at any stage. Request handling is driven directly and
bus.publish is captured, so no running bus is needed.

Runs under pytest or directly:  python tests/unit/test_sandbox.py
"""

import asyncio
import logging
import sys
from pathlib import Path

# Make src/ importable whether run via pytest or as a script.
_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import bus
import sandbox
from sandbox import (
    ActionApprovedEvent, ActionDeniedEvent, ActionRequestEvent,
    Capability, ViolationEvent,
)


# -- harness --------------------------------------------------------------------

_PUBLISHED: list = []


async def _collect(event) -> None:
    _PUBLISHED.append(event)


def _reset(stage: int = 0) -> None:
    _PUBLISHED.clear()
    bus.publish = _collect            # capture all emissions
    sandbox.init(stage=stage)
    sandbox._violation_count = 0


def _published(kind) -> list:
    return [e for e in _PUBLISHED if isinstance(e, kind)]


def _request(capability: Capability, module: str = "test_module") -> ActionRequestEvent:
    return ActionRequestEvent(source=module, timestamp=0.0,
                              requesting_module=module, capability=capability)


# -- capability unlocking -------------------------------------------------------

def test_stage_zero_allows_only_state_access():
    _reset(stage=0)

    assert sandbox.is_allowed(Capability.STATE_READ), "stage 0 must allow state reads"
    assert sandbox.is_allowed(Capability.STATE_WRITE), "stage 0 must allow state writes"
    for cap in (Capability.MICROPHONE_READ, Capability.AUDIO_OUTPUT, Capability.CAMERA_READ):
        assert not sandbox.is_allowed(cap), f"stage 0 must not allow {cap.name}"


def test_unlocks_are_cumulative_across_stages():
    _reset(stage=5)

    for cap in (Capability.STATE_READ, Capability.STATE_WRITE,
                Capability.MICROPHONE_READ, Capability.AUDIO_OUTPUT,
                Capability.CAMERA_READ):
        assert sandbox.is_allowed(cap), \
            f"stage 5 must retain {cap.name} unlocked at an earlier stage"


def test_capabilities_unlock_at_their_declared_stage():
    _reset(stage=1)
    assert sandbox.is_allowed(Capability.MICROPHONE_READ), "mic unlocks at stage 1"
    assert not sandbox.is_allowed(Capability.AUDIO_OUTPUT), "speaker must wait for stage 3"
    assert not sandbox.is_allowed(Capability.CAMERA_READ), "camera must wait for stage 5"

    _reset(stage=3)
    assert sandbox.is_allowed(Capability.AUDIO_OUTPUT), "speaker unlocks at stage 3"
    assert not sandbox.is_allowed(Capability.CAMERA_READ), "camera must wait for stage 5"


def test_advance_stage_grants_new_capabilities():
    _reset(stage=0)
    assert not sandbox.is_allowed(Capability.MICROPHONE_READ), "precondition"

    sandbox.advance_stage(1)

    assert sandbox.is_allowed(Capability.MICROPHONE_READ), "advancing must unlock the mic"
    assert sandbox._current_stage == 1, "current stage must be updated"


def test_advance_stage_never_regresses():
    """Development moves forward only - a lower stage must not revoke capabilities."""
    _reset(stage=5)

    sandbox.advance_stage(1)

    assert sandbox._current_stage == 5, "stage must not move backwards"
    assert sandbox.is_allowed(Capability.CAMERA_READ), "capabilities must not be revoked"


# -- the forbidden set ----------------------------------------------------------

def test_forbidden_capabilities_are_never_allowed():
    """Containment: no stage, however advanced, unlocks these."""
    for stage in (0, 1, 3, 5, 11, 99):
        _reset(stage=stage)
        for cap in (Capability.NETWORK, Capability.GENOME_MODIFY, Capability.SANDBOX_MODIFY):
            assert not sandbox.is_allowed(cap), \
                f"{cap.name} must never be allowed (checked at stage {stage})"


def test_forbidden_capability_is_not_reachable_via_advance_stage():
    _reset(stage=0)

    sandbox.advance_stage(99)

    assert not sandbox.is_allowed(Capability.NETWORK), \
        "advancing to an arbitrary stage must not unlock the network"
    assert sandbox._FORBIDDEN.isdisjoint(sandbox._allowed), \
        "no forbidden capability may enter the allowed set"


# -- request handling -----------------------------------------------------------

def test_allowed_request_is_approved():
    _reset(stage=0)

    asyncio.run(sandbox.handle_request(_request(Capability.STATE_READ)))

    approved = _published(ActionApprovedEvent)
    assert len(approved) == 1, "an allowed capability must be approved"
    assert approved[0].capability is Capability.STATE_READ, "approval must name the capability"
    assert approved[0].requesting_module == "test_module", "approval must name the requester"
    assert _published(ActionDeniedEvent) == [], "no denial may be emitted"
    assert _published(ViolationEvent) == [], "an allowed request is not a violation"


def test_locked_request_is_denied_not_treated_as_violation():
    """Asking for a capability not yet grown into is normal, not an attack."""
    _reset(stage=0)

    asyncio.run(sandbox.handle_request(_request(Capability.CAMERA_READ)))

    denied = _published(ActionDeniedEvent)
    assert len(denied) == 1, "a locked capability must be denied"
    assert denied[0].capability is Capability.CAMERA_READ, "denial must name the capability"
    assert "stage" in denied[0].reason, "denial must explain the stage gate"
    assert _published(ViolationEvent) == [], "a stage-locked request is not a violation"
    assert sandbox._violation_count == 0, "the violation counter must not move"


def test_forbidden_request_raises_a_violation():
    _reset(stage=5)

    logging.getLogger("sandbox").setLevel(logging.CRITICAL)
    try:
        for cap in (Capability.NETWORK, Capability.GENOME_MODIFY, Capability.SANDBOX_MODIFY):
            asyncio.run(sandbox.handle_request(_request(cap)))
    finally:
        logging.getLogger("sandbox").setLevel(logging.NOTSET)

    violations = _published(ViolationEvent)
    assert len(violations) == 3, "each forbidden request must raise a violation"
    assert {v.capability for v in violations} == {
        Capability.NETWORK, Capability.GENOME_MODIFY, Capability.SANDBOX_MODIFY
    }, "violations must name the requested capabilities"
    assert sandbox._violation_count == 3, "the violation counter must track every attempt"
    assert _published(ActionApprovedEvent) == [], "a forbidden request must never be approved"


def test_forbidden_request_is_never_approved_at_any_stage():
    logging.getLogger("sandbox").setLevel(logging.CRITICAL)
    try:
        for stage in (0, 1, 3, 5, 11, 99):
            _reset(stage=stage)
            asyncio.run(sandbox.handle_request(_request(Capability.NETWORK)))
            assert _published(ActionApprovedEvent) == [], \
                f"network must not be approved at stage {stage}"
            assert len(_published(ViolationEvent)) == 1, \
                f"network request must be a violation at stage {stage}"
    finally:
        logging.getLogger("sandbox").setLevel(logging.NOTSET)


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
