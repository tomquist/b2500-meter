"""Per-battery efficiency-window weight in the LoadBalancer.

The efficiency rotation deprioritizes some batteries at low demand (so the
active ones stay above ``min_efficient_power``) and rotates which one is active
for fair wear. ``efficiency_window_weight`` (a report-dict field, ``[0, 1]``,
neutral ``1.0``) biases that rotation: ``0.0`` parks a battery while limiting,
``1.0`` is full participation, and the active head holds its slot for
``efficiency_rotation_interval`` scaled by its weight.

These poke the balancer internals (``_priority`` / ``_deprioritized`` /
``_last_rotation``) directly, matching the existing balancer unit tests. The
C++ mirror is covered by the differential parity suite.
"""

import time

from astrameter.ct002.balancer import (
    BalancerConfig,
    ConsumerReport,
    LoadBalancer,
)


class _FakeClock:
    def __init__(self) -> None:
        self._t = time.time()

    def __call__(self) -> float:
        return self._t

    def advance(self, dt: float) -> None:
        self._t += dt


def _make_balancer(clock, *, rotation_interval: float = 900.0) -> LoadBalancer:
    return LoadBalancer(
        config=BalancerConfig(
            fair_distribution=True,
            min_efficient_power=150,
            efficiency_rotation_interval=rotation_interval,
            # Follow demand instantly so the active-set decision is deterministic
            # (no EMA smoothing) for these unit assertions.
            efficiency_demand_alpha=1.0,
        ),
        saturation_alpha=0.15,
        saturation_min_target=20,
        saturation_decay_factor=0.995,
        saturation_grace_seconds=90.0,
        saturation_stall_timeout_seconds=60.0,
        saturation_enabled=False,
        clock=clock,
    )


def _report(power: float, eff_weight: float = 1.0) -> ConsumerReport:
    return ConsumerReport(
        phase="A",
        power=power,
        device_type="HMG-50",
        efficiency_window_weight=eff_weight,
    )


def test_zero_weight_battery_stays_deprioritized_while_limiting() -> None:
    """A 0-weight battery is parked while limiting (enough non-zero peers)."""
    clock = _FakeClock()
    lb = _make_balancer(clock)
    # abs demand 200 over two units => per-consumer 100 < 150 => limiting,
    # one active slot. "a" (full weight) stays active; "b" (0) is parked.
    reports = {"a": _report(0.0, 1.0), "b": _report(0.0, 0.0)}
    for i in range(3):
        clock.advance(1.0)
        lb._compute_efficiency_deprioritized(reports, (i,), 200.0)
    assert lb._deprioritized == {"b"}
    # Order: the zero-weight unit is sunk to the back of the priority list.
    assert lb._priority[0] == "a"
    assert lb._priority[-1] == "b"


def test_zero_weight_battery_runs_when_all_needed() -> None:
    """When demand needs every battery (slots == n), the 0-weight one runs too."""
    clock = _FakeClock()
    lb = _make_balancer(clock)
    # abs demand 600 over two units => per-consumer 300 >= 150 => no limiting.
    reports = {"a": _report(0.0, 1.0), "b": _report(0.0, 0.0)}
    for i in range(3):
        clock.advance(1.0)
        lb._compute_efficiency_deprioritized(reports, (i,), 600.0)
    assert lb._deprioritized == set()


def test_low_weight_battery_sinks_below_alphabetical_order() -> None:
    """The weight sort overrides the alphabetical fill order."""
    clock = _FakeClock()
    lb = _make_balancer(clock)
    # "a" sorts first alphabetically but has the lower weight, so it must end up
    # behind "b" once the descending-by-weight stable sort runs.
    reports = {"a": _report(0.0, 0.2), "b": _report(0.0, 1.0)}
    clock.advance(1.0)
    lb._compute_efficiency_deprioritized(reports, (0,), 200.0)
    assert lb._priority[0] == "b"
    assert lb._priority[-1] == "a"
    assert lb._deprioritized == {"a"}


def test_full_weight_head_rotates_after_full_interval() -> None:
    """A weight-1.0 head holds its slot for the whole rotation interval."""
    clock = _FakeClock()
    lb = _make_balancer(clock, rotation_interval=900.0)
    reports = {"a": _report(0.0, 1.0), "b": _report(0.0, 1.0)}
    clock.advance(1.0)
    lb._compute_efficiency_deprioritized(reports, (0,), 200.0)
    rot0 = lb._last_rotation

    # Half the interval: no rotation yet.
    clock.advance(450.0)
    lb._compute_efficiency_deprioritized(reports, (1,), 200.0)
    assert lb._last_rotation == rot0

    # Past the full interval: the head rotates out.
    clock.advance(500.0)
    lb._compute_efficiency_deprioritized(reports, (2,), 200.0)
    assert lb._last_rotation > rot0


def test_half_weight_head_rotates_after_half_interval() -> None:
    """A weight-0.5 head gives up its slot after ~half the interval."""
    clock = _FakeClock()
    lb = _make_balancer(clock, rotation_interval=900.0)
    reports = {"a": _report(0.0, 0.5), "b": _report(0.0, 0.5)}
    clock.advance(1.0)
    lb._compute_efficiency_deprioritized(reports, (0,), 200.0)
    rot0 = lb._last_rotation

    # Just under half the interval: not yet.
    clock.advance(440.0)
    lb._compute_efficiency_deprioritized(reports, (1,), 200.0)
    assert lb._last_rotation == rot0

    # Past half the interval (900 * 0.5 = 450): the head rotates out early.
    clock.advance(20.0)
    lb._compute_efficiency_deprioritized(reports, (2,), 200.0)
    assert lb._last_rotation > rot0


def _run_rotation(
    lb: LoadBalancer,
    clock: _FakeClock,
    weights: dict[str, float],
    *,
    minutes: int,
    load: float = 200.0,
) -> dict[str, int]:
    """Minutes each battery spends active over *minutes* one-minute polls.

    Feeds the balancer back what its own decision implies: whoever holds an
    active slot reports its share of *load* on the next poll, and a
    deprioritized battery reports 0.  A battery reporting 0 W while active
    reads as one that cannot follow its target, which sends the efficiency
    probe hunting instead of leaving the rotation to run.
    """
    power = dict.fromkeys(weights, load / len(weights))
    active_minutes = dict.fromkeys(weights, 0)
    for i in range(minutes):
        clock.advance(60.0)
        reports = {cid: _report(power[cid], weights[cid]) for cid in weights}
        deprioritized = lb._compute_efficiency_deprioritized(reports, (i,), 0.0)
        active = [cid for cid in weights if cid not in deprioritized]
        for cid in weights:
            power[cid] = load / len(active) if cid in active else 0.0
        for cid in active:
            active_minutes[cid] += 1
    return active_minutes


def test_unequal_weights_split_active_time_in_proportion() -> None:
    """Issue #647: a half-weight battery gets half the active time, not one poll.

    Two batteries in a 1:2 capacity ratio at a demand only one of them should
    serve.  Weights 0.5 / 1.0 are meant to hand the small one half the active
    window the large one gets; before the fix the every-poll weight sort put the
    large one straight back at the head, leaving the small one a single poll per
    cycle (a ~14:1 split rather than 2:1).
    """
    clock = _FakeClock()
    lb = _make_balancer(clock, rotation_interval=900.0)

    active = _run_rotation(lb, clock, {"small": 0.5, "large": 1.0}, minutes=120)

    assert active["small"] > 0
    assert 1.8 <= active["large"] / active["small"] <= 2.2


def test_equal_weights_split_active_time_evenly() -> None:
    """The neutral case stays even — the fix must not skew a 1:1 pool."""
    clock = _FakeClock()
    lb = _make_balancer(clock, rotation_interval=900.0)

    active = _run_rotation(lb, clock, {"a": 1.0, "b": 1.0}, minutes=120)

    assert 0.8 <= active["a"] / active["b"] <= 1.2


def test_weight_sort_does_not_re_pin_the_head_every_tick() -> None:
    """The weight order is a fill order, not a permanent rank.

    Once the head rotates out it must stay out for the next battery's whole
    window; re-sorting by weight on every poll would hand the slot straight
    back to the heaviest battery.
    """
    clock = _FakeClock()
    lb = _make_balancer(clock, rotation_interval=900.0)
    reports = {"a": _report(0.0, 0.4), "b": _report(0.0, 1.0)}

    # First tick fills the order by weight: the heavier battery leads.
    clock.advance(1.0)
    lb._compute_efficiency_deprioritized(reports, (0,), 200.0)
    assert lb._priority[0] == "b"

    # "b" holds a full interval, then hands over to "a" ...
    clock.advance(901.0)
    lb._compute_efficiency_deprioritized(reports, (1,), 200.0)
    assert lb._priority[0] == "a"

    # ... and keeps it for its own (shorter) window instead of being displaced
    # on the very next poll.
    clock.advance(60.0)
    lb._compute_efficiency_deprioritized(reports, (2,), 200.0)
    assert lb._priority[0] == "a"
