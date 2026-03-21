"""Tests for nexa_mfrr_eam.timing module.

Covers MTU dataclass, gate_closure(), current_mtu(), mtu_range(),
and evaluate_conditional_availability().
"""

from __future__ import annotations

import datetime

import pytest
from nexa_mfrr_eam.exceptions import InvalidMTUError, NaiveDatetimeError
from nexa_mfrr_eam.timing import (
    MTU,
    GateClosure,
    MARIMode,
    current_mtu,
    evaluate_conditional_availability,
    gate_closure,
    mtu_range,
)

UTC = datetime.UTC


# ---------------------------------------------------------------------------
# Group A: MTU dataclass
# ---------------------------------------------------------------------------


class TestMTUDataclass:
    def test_construction(self) -> None:
        start = datetime.datetime(2026, 3, 21, 10, 0, tzinfo=UTC)
        end = datetime.datetime(2026, 3, 21, 10, 15, tzinfo=UTC)
        mtu = MTU(start=start, end=end)
        assert mtu.start == start
        assert mtu.end == end

    def test_duration_is_15_minutes(self) -> None:
        start = datetime.datetime(2026, 3, 21, 10, 0, tzinfo=UTC)
        end = start + datetime.timedelta(minutes=15)
        mtu = MTU(start=start, end=end)
        assert mtu.end - mtu.start == datetime.timedelta(minutes=15)

    def test_frozen(self) -> None:
        mtu = MTU(
            start=datetime.datetime(2026, 3, 21, 10, 0, tzinfo=UTC),
            end=datetime.datetime(2026, 3, 21, 10, 15, tzinfo=UTC),
        )
        with pytest.raises((AttributeError, TypeError)):
            mtu.start = datetime.datetime(2026, 3, 21, 11, 0, tzinfo=UTC)  # type: ignore[misc]

    def test_equality(self) -> None:
        start = datetime.datetime(2026, 3, 21, 10, 0, tzinfo=UTC)
        end = start + datetime.timedelta(minutes=15)
        assert MTU(start=start, end=end) == MTU(start=start, end=end)

    def test_inequality(self) -> None:
        s1 = datetime.datetime(2026, 3, 21, 10, 0, tzinfo=UTC)
        s2 = datetime.datetime(2026, 3, 21, 10, 15, tzinfo=UTC)
        td = datetime.timedelta(minutes=15)
        assert MTU(s1, s1 + td) != MTU(s2, s2 + td)

    def test_midnight_mtu(self) -> None:
        start = datetime.datetime(2026, 3, 21, 0, 0, tzinfo=UTC)
        mtu = MTU(start=start, end=start + datetime.timedelta(minutes=15))
        assert mtu.start.hour == 0
        assert mtu.start.minute == 0

    def test_end_of_day_mtu(self) -> None:
        start = datetime.datetime(2026, 3, 21, 23, 45, tzinfo=UTC)
        mtu = MTU(start=start, end=start + datetime.timedelta(minutes=15))
        assert mtu.end == datetime.datetime(2026, 3, 22, 0, 0, tzinfo=UTC)

    def test_repr_contains_start(self) -> None:
        start = datetime.datetime(2026, 3, 21, 10, 0, tzinfo=UTC)
        mtu = MTU(start=start, end=start + datetime.timedelta(minutes=15))
        assert "2026" in repr(mtu)


# ---------------------------------------------------------------------------
# Group B: gate_closure() – Pre-MARI
# ---------------------------------------------------------------------------


class TestGateClosurePreMARI:
    @pytest.fixture()
    def gc(self) -> GateClosure:
        mtu_start = datetime.datetime(2026, 3, 21, 10, 0, tzinfo=UTC)
        return gate_closure(mtu_start, mari_mode=MARIMode.PRE_MARI)

    def test_bsp_gct_is_qh_minus_45(self, gc: GateClosure) -> None:
        expected = datetime.datetime(2026, 3, 21, 9, 15, tzinfo=UTC)
        assert gc.bsp_gct == expected

    def test_tso_gct_is_qh_minus_15(self, gc: GateClosure) -> None:
        expected = datetime.datetime(2026, 3, 21, 9, 45, tzinfo=UTC)
        assert gc.tso_gct == expected

    def test_aof_run_is_qh_minus_14(self, gc: GateClosure) -> None:
        expected = datetime.datetime(2026, 3, 21, 9, 46, tzinfo=UTC)
        assert gc.aof_run == expected

    def test_activation_is_qh_minus_7m30s(self, gc: GateClosure) -> None:
        expected = datetime.datetime(2026, 3, 21, 9, 52, 30, tzinfo=UTC)
        assert gc.activation == expected

    def test_mari_mode_is_pre_mari(self, gc: GateClosure) -> None:
        assert gc.mari_mode is MARIMode.PRE_MARI

    def test_is_gate_open_before_bsp_gct(self, gc: GateClosure) -> None:
        before = datetime.datetime(2026, 3, 21, 9, 0, tzinfo=UTC)
        assert gc.is_gate_open(now=before) is True

    def test_is_gate_open_after_bsp_gct(self, gc: GateClosure) -> None:
        after = datetime.datetime(2026, 3, 21, 9, 30, tzinfo=UTC)
        assert gc.is_gate_open(now=after) is False

    def test_is_gate_open_at_exact_bsp_gct(self, gc: GateClosure) -> None:
        at_gct = datetime.datetime(2026, 3, 21, 9, 15, tzinfo=UTC)
        # At exactly GCT the gate is closed (not strictly before)
        assert gc.is_gate_open(now=at_gct) is False

    def test_is_gate_open_naive_raises(self, gc: GateClosure) -> None:
        naive = datetime.datetime(2026, 3, 21, 9, 0)
        with pytest.raises(NaiveDatetimeError):
            gc.is_gate_open(now=naive)

    def test_default_mari_mode_is_pre_mari(self) -> None:
        mtu_start = datetime.datetime(2026, 3, 21, 10, 0, tzinfo=UTC)
        gc = gate_closure(mtu_start)
        assert gc.mari_mode is MARIMode.PRE_MARI

    def test_naive_mtu_start_raises(self) -> None:
        naive = datetime.datetime(2026, 3, 21, 10, 0)
        with pytest.raises(NaiveDatetimeError):
            gate_closure(naive)

    def test_non_boundary_minute_raises(self) -> None:
        bad = datetime.datetime(2026, 3, 21, 10, 7, tzinfo=UTC)
        with pytest.raises(InvalidMTUError):
            gate_closure(bad)

    def test_non_zero_seconds_raises(self) -> None:
        bad = datetime.datetime(2026, 3, 21, 10, 0, 1, tzinfo=UTC)
        with pytest.raises(InvalidMTUError):
            gate_closure(bad)


# ---------------------------------------------------------------------------
# Group C: gate_closure() – Post-MARI
# ---------------------------------------------------------------------------


class TestGateClosurePostMARI:
    @pytest.fixture()
    def gc(self) -> GateClosure:
        mtu_start = datetime.datetime(2026, 3, 21, 10, 0, tzinfo=UTC)
        return gate_closure(mtu_start, mari_mode=MARIMode.POST_MARI)

    def test_bsp_gct_is_qh_minus_25(self, gc: GateClosure) -> None:
        expected = datetime.datetime(2026, 3, 21, 9, 35, tzinfo=UTC)
        assert gc.bsp_gct == expected

    def test_tso_gct_is_qh_minus_12(self, gc: GateClosure) -> None:
        expected = datetime.datetime(2026, 3, 21, 9, 48, tzinfo=UTC)
        assert gc.tso_gct == expected

    def test_aof_run_is_qh_minus_10(self, gc: GateClosure) -> None:
        expected = datetime.datetime(2026, 3, 21, 9, 50, tzinfo=UTC)
        assert gc.aof_run == expected

    def test_activation_still_qh_minus_7m30s(self, gc: GateClosure) -> None:
        expected = datetime.datetime(2026, 3, 21, 9, 52, 30, tzinfo=UTC)
        assert gc.activation == expected

    def test_mari_mode_is_post_mari(self, gc: GateClosure) -> None:
        assert gc.mari_mode is MARIMode.POST_MARI

    def test_non_utc_tz_input_normalised_to_utc(self) -> None:
        # Input in CET (UTC+1) should normalise to UTC correctly
        cet = datetime.timezone(datetime.timedelta(hours=1))
        mtu_cet = datetime.datetime(2026, 3, 21, 11, 0, tzinfo=cet)  # = 10:00 UTC
        gc = gate_closure(mtu_cet, mari_mode=MARIMode.POST_MARI)
        assert gc.mtu_start == datetime.datetime(2026, 3, 21, 10, 0, tzinfo=UTC)

    def test_post_mari_bsp_gct_later_than_pre_mari(self) -> None:
        mtu_start = datetime.datetime(2026, 3, 21, 10, 0, tzinfo=UTC)
        pre = gate_closure(mtu_start, MARIMode.PRE_MARI)
        post = gate_closure(mtu_start, MARIMode.POST_MARI)
        assert post.bsp_gct > pre.bsp_gct  # QH-25 is later than QH-45


# ---------------------------------------------------------------------------
# Group D: current_mtu()
# ---------------------------------------------------------------------------


class TestCurrentMTU:
    def test_on_boundary(self) -> None:
        t = datetime.datetime(2026, 3, 21, 10, 0, tzinfo=UTC)
        mtu = current_mtu(t)
        assert mtu.start == t
        assert mtu.end == datetime.datetime(2026, 3, 21, 10, 15, tzinfo=UTC)

    def test_mid_interval(self) -> None:
        t = datetime.datetime(2026, 3, 21, 10, 7, 30, tzinfo=UTC)
        mtu = current_mtu(t)
        assert mtu.start == datetime.datetime(2026, 3, 21, 10, 0, tzinfo=UTC)
        assert mtu.end == datetime.datetime(2026, 3, 21, 10, 15, tzinfo=UTC)

    def test_just_before_boundary(self) -> None:
        t = datetime.datetime(2026, 3, 21, 10, 14, 59, tzinfo=UTC)
        mtu = current_mtu(t)
        assert mtu.start == datetime.datetime(2026, 3, 21, 10, 0, tzinfo=UTC)

    def test_quarter_hour_0(self) -> None:
        t = datetime.datetime(2026, 3, 21, 10, 0, tzinfo=UTC)
        assert current_mtu(t).start.minute == 0

    def test_quarter_hour_15(self) -> None:
        t = datetime.datetime(2026, 3, 21, 10, 20, tzinfo=UTC)
        assert current_mtu(t).start.minute == 15

    def test_quarter_hour_30(self) -> None:
        t = datetime.datetime(2026, 3, 21, 10, 32, tzinfo=UTC)
        assert current_mtu(t).start.minute == 30

    def test_quarter_hour_45(self) -> None:
        t = datetime.datetime(2026, 3, 21, 10, 50, tzinfo=UTC)
        assert current_mtu(t).start.minute == 45

    def test_no_args_returns_mtu(self) -> None:
        mtu = current_mtu()
        assert isinstance(mtu, MTU)
        assert mtu.start.tzinfo is not None
        assert mtu.end - mtu.start == datetime.timedelta(minutes=15)

    def test_naive_raises(self) -> None:
        naive = datetime.datetime(2026, 3, 21, 10, 0)
        with pytest.raises(NaiveDatetimeError):
            current_mtu(naive)

    def test_midnight_crossing(self) -> None:
        # 23:50 is in the 23:45 MTU
        t = datetime.datetime(2026, 3, 21, 23, 50, tzinfo=UTC)
        mtu = current_mtu(t)
        assert mtu.start == datetime.datetime(2026, 3, 21, 23, 45, tzinfo=UTC)
        assert mtu.end == datetime.datetime(2026, 3, 22, 0, 0, tzinfo=UTC)


# ---------------------------------------------------------------------------
# Group E: mtu_range()
# ---------------------------------------------------------------------------


class TestMTURange:
    def test_full_day_96_mtus(self) -> None:
        mtus = mtu_range("2026-03-21T00:00Z", "2026-03-22T00:00Z")
        assert len(mtus) == 96

    def test_returns_mtu_instances(self) -> None:
        mtus = mtu_range("2026-03-21T00:00Z", "2026-03-21T01:00Z")
        assert all(isinstance(m, MTU) for m in mtus)

    def test_first_mtu_starts_at_start(self) -> None:
        mtus = mtu_range("2026-03-21T10:00Z", "2026-03-21T11:00Z")
        assert mtus[0].start == datetime.datetime(2026, 3, 21, 10, 0, tzinfo=UTC)

    def test_last_mtu_ends_at_end(self) -> None:
        mtus = mtu_range("2026-03-21T10:00Z", "2026-03-21T11:00Z")
        assert mtus[-1].end == datetime.datetime(2026, 3, 21, 11, 0, tzinfo=UTC)

    def test_consecutive_mtus(self) -> None:
        mtus = mtu_range("2026-03-21T10:00Z", "2026-03-21T11:00Z")
        for i in range(1, len(mtus)):
            assert mtus[i].start == mtus[i - 1].end

    def test_one_hour_gives_4_mtus(self) -> None:
        mtus = mtu_range("2026-03-21T10:00Z", "2026-03-21T11:00Z")
        assert len(mtus) == 4

    def test_single_mtu(self) -> None:
        mtus = mtu_range("2026-03-21T10:00Z", "2026-03-21T10:15Z")
        assert len(mtus) == 1

    def test_dst_spring_forward_92_mtus(self) -> None:
        # Spring-forward 2026-03-29: 23:00→22:00 UTC = 23h = 92 MTUs.
        mtus = mtu_range("2026-03-28T23:00Z", "2026-03-29T22:00Z", tz="CET")
        assert len(mtus) == 92

    def test_dst_fall_back_100_mtus(self) -> None:
        # Fall-back 2026-10-25: 22:00→23:00 UTC = 25h = 100 MTUs.
        mtus = mtu_range("2026-10-24T22:00Z", "2026-10-25T23:00Z", tz="CET")
        assert len(mtus) == 100

    def test_tz_param_accepted(self) -> None:
        # tz param should not raise even though it's informational only
        mtus = mtu_range("2026-03-21T00:00Z", "2026-03-22T00:00Z", tz="CET")
        assert len(mtus) == 96

    def test_string_inputs_parsed(self) -> None:
        mtus = mtu_range("2026-03-21T10:00Z", "2026-03-21T10:30Z")
        assert len(mtus) == 2

    def test_datetime_inputs_accepted(self) -> None:
        start = datetime.datetime(2026, 3, 21, 10, 0, tzinfo=UTC)
        end = datetime.datetime(2026, 3, 21, 11, 0, tzinfo=UTC)
        mtus = mtu_range(start, end)
        assert len(mtus) == 4

    def test_empty_range_raises(self) -> None:
        with pytest.raises(ValueError, match="start must be strictly before end"):
            mtu_range("2026-03-21T10:00Z", "2026-03-21T09:00Z")

    def test_equal_start_end_raises(self) -> None:
        with pytest.raises(ValueError):
            mtu_range("2026-03-21T10:00Z", "2026-03-21T10:00Z")


# ---------------------------------------------------------------------------
# Group F: evaluate_conditional_availability()
# ---------------------------------------------------------------------------


class TestEvaluateConditionalAvailability:
    def test_a65_a55_activated_is_unavailable(self) -> None:
        # README example: A65 + A55 + activated → False
        result = evaluate_conditional_availability(
            bid_status="A65",
            links=[{"condition": "A55", "linked_bid_activated": True}],
        )
        assert result is False

    def test_a65_a55_not_activated_is_available(self) -> None:
        result = evaluate_conditional_availability(
            bid_status="A65",
            links=[{"condition": "A55", "linked_bid_activated": False}],
        )
        assert result is True

    def test_non_a65_always_available(self) -> None:
        result = evaluate_conditional_availability(
            bid_status="A06",  # e.g. "available"
            links=[{"condition": "A55", "linked_bid_activated": True}],
        )
        assert result is True

    def test_empty_links_available(self) -> None:
        result = evaluate_conditional_availability(bid_status="A65", links=[])
        assert result is True

    def test_a56_linked_activated_is_available(self) -> None:
        # A56: available IF activated; linked bid was activated → available
        result = evaluate_conditional_availability(
            bid_status="A65",
            links=[{"condition": "A56", "linked_bid_activated": True}],
        )
        assert result is True

    def test_a56_linked_not_activated_is_unavailable(self) -> None:
        # A56: available IF activated; linked bid was NOT activated → unavailable
        result = evaluate_conditional_availability(
            bid_status="A65",
            links=[{"condition": "A56", "linked_bid_activated": False}],
        )
        assert result is False

    def test_multiple_links_one_blocks(self) -> None:
        result = evaluate_conditional_availability(
            bid_status="A65",
            links=[
                {"condition": "A55", "linked_bid_activated": False},  # does not block
                {"condition": "A55", "linked_bid_activated": True},  # blocks
            ],
        )
        assert result is False

    def test_multiple_links_all_pass(self) -> None:
        result = evaluate_conditional_availability(
            bid_status="A65",
            links=[
                {"condition": "A55", "linked_bid_activated": False},
                {"condition": "A56", "linked_bid_activated": True},
            ],
        )
        assert result is True

    def test_unknown_condition_ignored(self) -> None:
        # Future condition codes should not block the bid
        result = evaluate_conditional_availability(
            bid_status="A65",
            links=[{"condition": "A99", "linked_bid_activated": True}],
        )
        assert result is True
