"""Tests for the cryopod formatting module."""

from cryopod.formatting import format_size, format_timestamp


class TestFormatSize:
    """Tests for format_size helper."""

    def test_bytes(self):
        assert format_size(500) == "500 B"

    def test_zero(self):
        assert format_size(0) == "0 B"

    def test_kilobytes(self):
        assert format_size(2150) == "2.1 KB"

    def test_megabytes(self):
        assert format_size(1_400_000) == "1.3 MB"

    def test_gigabytes(self):
        assert format_size(1_500_000_000) == "1.4 GB"


class TestFormatTimestamp:
    """Tests for format_timestamp helper."""

    def test_format_iso_timestamp(self):
        """ISO string formatted correctly."""
        result = format_timestamp("2026-03-07T14:32:00")
        assert result == "2026-03-07 14:32"

    def test_format_timestamp_with_timezone(self):
        """Timezone-aware string handled."""
        result = format_timestamp("2026-03-07T14:32:00+00:00")
        assert result == "2026-03-07 14:32"
