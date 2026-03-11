"""Tests for date/time formatting helpers."""

from datetime import datetime, date
from zoneinfo import ZoneInfo

import pytest

from app.services.calendar import (
    _format_time_range,
    _format_time_short,
    _format_day_label,
    _describe_period,
)

ET = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")


class TestFormatTimeRange:
    def test_same_day(self):
        start = datetime(2026, 3, 10, 14, 0, tzinfo=ET)
        end = datetime(2026, 3, 10, 15, 0, tzinfo=ET)
        result = _format_time_range(start, end, ET)
        assert "Mar 10" in result
        assert "2:00 PM" in result
        assert "3:00 PM" in result

    def test_different_days(self):
        start = datetime(2026, 3, 10, 14, 0, tzinfo=ET)
        end = datetime(2026, 3, 11, 10, 0, tzinfo=ET)
        result = _format_time_range(start, end, ET)
        assert "Mar 10" in result
        assert "Mar 11" in result

    def test_utc_to_local_conversion(self):
        """Times stored in UTC should display in user's timezone."""
        # March 10 2026 is after DST spring-forward, so ET = UTC-4
        # 7pm UTC = 3pm ET (UTC-4)
        start = datetime(2026, 3, 10, 19, 0, tzinfo=UTC)
        end = datetime(2026, 3, 10, 20, 0, tzinfo=UTC)
        result = _format_time_range(start, end, ET)
        assert "3:00 PM" in result
        assert "4:00 PM" in result


class TestFormatTimeShort:
    def test_basic(self):
        dt = datetime(2026, 3, 10, 14, 30, tzinfo=ET)
        assert "2:30 PM" in _format_time_short(dt, ET)

    def test_midnight(self):
        dt = datetime(2026, 3, 10, 0, 0, tzinfo=ET)
        result = _format_time_short(dt, ET)
        assert "12:00 AM" in result


class TestFormatDayLabel:
    def test_today(self):
        today = date(2026, 3, 10)
        assert _format_day_label(today, today) == "Today"

    def test_tomorrow(self):
        today = date(2026, 3, 10)
        tomorrow = date(2026, 3, 11)
        assert _format_day_label(tomorrow, today) == "Tomorrow"

    def test_yesterday(self):
        today = date(2026, 3, 10)
        yesterday = date(2026, 3, 9)
        assert _format_day_label(yesterday, today) == "Yesterday"

    def test_this_week(self):
        today = date(2026, 3, 10)  # Tuesday
        friday = date(2026, 3, 13)
        result = _format_day_label(friday, today)
        assert result == "Friday"

    def test_far_future(self):
        today = date(2026, 3, 10)
        far = date(2026, 4, 15)
        result = _format_day_label(far, today)
        assert "Apr 15" in result


class TestDescribePeriod:
    def test_today(self):
        now = datetime.now(ET)
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = now.replace(hour=23, minute=59, second=59, microsecond=0)
        result = _describe_period(start, end, ET)
        assert "today" in result.lower()
