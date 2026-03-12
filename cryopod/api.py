"""Shared API helpers for Cryopod CLI."""

from contextlib import contextmanager

import click
import httpx


def raise_for_status(resp: httpx.Response, context: str = "") -> None:
    """Raise a ClickException for non-success HTTP responses.

    Handles 401/403 auth errors, 404 not found, and generic API errors.
    The context string is used in 404 messages (e.g. 'Pod "claude" not found.').
    """
    if resp.status_code in (401, 403):
        raise click.ClickException(
            f"Authentication failed ({resp.status_code}). Check your CRYOPOD_API_KEY."
        )

    if resp.status_code == 404:
        msg = f"{context} not found." if context else "Not found."
        raise click.ClickException(msg)

    try:
        detail = resp.json().get("detail", resp.text)
    except Exception:
        detail = resp.text
    raise click.ClickException(f"API error ({resp.status_code}): {detail}")


@contextmanager
def api_errors():
    """Context manager that catches httpx network errors and re-raises as ClickException."""
    try:
        yield
    except httpx.ConnectError as err:
        raise click.ClickException(
            "Could not connect to Cryopod API. Check your network connection."
        ) from err
    except httpx.TimeoutException as err:
        raise click.ClickException(
            "Connection to Cryopod API timed out. Try again later."
        ) from err
