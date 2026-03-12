"""Shared formatting utilities for Cryopod CLI."""

from datetime import datetime


def format_size(size_bytes: int) -> str:
    """Format byte count as a human-readable size string."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"


def format_timestamp(iso_str: str) -> str:
    """Convert ISO 8601 datetime string to human-readable format."""
    dt = datetime.fromisoformat(iso_str)
    return dt.strftime("%Y-%m-%d %H:%M")
