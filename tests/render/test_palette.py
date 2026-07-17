"""Tests for the shared colour palette primitives."""

from __future__ import annotations

from assertpy import assert_that

from git_replay.render.palette import PLASMA, lerp, plasma


def test_plasma_at_zero_returns_first_stop() -> None:
    """``plasma(0)`` samples the first plasma stop exactly."""
    red, green, blue = PLASMA[0]
    assert_that(plasma(0.0)).is_equal_to(f"rgb({red},{green},{blue})")


def test_plasma_at_one_returns_last_stop() -> None:
    """``plasma(1)`` samples the final plasma stop exactly."""
    red, green, blue = PLASMA[-1]
    assert_that(plasma(1.0)).is_equal_to(f"rgb({red},{green},{blue})")


def test_plasma_clamps_below_zero_to_first_stop() -> None:
    """Positions below zero clamp to the first plasma stop."""
    assert_that(plasma(-0.5)).is_equal_to(plasma(0.0))


def test_plasma_clamps_above_one_to_last_stop() -> None:
    """Positions above one clamp to the last plasma stop."""
    assert_that(plasma(1.5)).is_equal_to(plasma(1.0))


def test_plasma_midpoint_interpolates_between_stops() -> None:
    """``plasma(0.5)`` sits on the central plasma stop for five stops."""
    red, green, blue = PLASMA[2]
    assert_that(plasma(0.5)).is_equal_to(f"rgb({red},{green},{blue})")


def test_lerp_returns_endpoints_and_midpoint() -> None:
    """``lerp`` returns the endpoints at 0/1 and the mean at 0.5."""
    assert_that(lerp(start=10.0, end=20.0, ratio=0.0)).is_equal_to(10.0)
    assert_that(lerp(start=10.0, end=20.0, ratio=1.0)).is_equal_to(20.0)
    assert_that(lerp(start=10.0, end=20.0, ratio=0.5)).is_equal_to(15.0)
