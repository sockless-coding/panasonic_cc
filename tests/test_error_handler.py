"""Tests for turning API errors into friendly messages."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from aiohttp import ClientResponseError

from custom_components.panasonic_cc.error_handler import (
    ErrorCategory,
    classify_error,
    friendly_error_for_command_failure,
)


def response_error(status: int) -> ClientResponseError:
    """Build an aiohttp error with the given status and an empty message."""
    return ClientResponseError(MagicMock(), (), status=status, message="")


@pytest.mark.parametrize(
    ("message", "category", "title"),
    [
        ("Expected status code '200' but received '500'", ErrorCategory.SERVER_ERROR, "Server Error"),
        ("Expected status code '200' but received '429'", ErrorCategory.RATE_LIMIT, "Rate Limited"),
        ('{"code":5005,"message":"Adapter Communication error"}', ErrorCategory.ADAPTER_COMMUNICATION, "Device Communication Error"),
        ('{"code": 5001}', ErrorCategory.ADAPTER_COMMUNICATION, "Device Not Responding"),
        ("HTTP 401 returned", ErrorCategory.AUTHENTICATION, "Authentication Failed"),
        ("got a 503 from the server", ErrorCategory.SERVER_ERROR, "Service Unavailable"),
        ("Adapter communication error", ErrorCategory.ADAPTER_COMMUNICATION, "Device Communication Error"),
        ("Device not responding", ErrorCategory.ADAPTER_COMMUNICATION, "Device Not Responding"),
        ("The request timed out", ErrorCategory.NETWORK, "Connection Timeout"),
        ("Invalid token", ErrorCategory.AUTHENTICATION, "Authentication Error"),
        ("Too many requests", ErrorCategory.RATE_LIMIT, "Rate Limited"),
        ("Down for maintenance", ErrorCategory.SERVER_ERROR, "Service Unavailable"),
    ],
)
def test_classify_error_from_message(
    message: str, category: ErrorCategory, title: str
) -> None:
    """Codes and known phrases in the message pick the matching error."""
    friendly = classify_error(Exception(message))

    assert friendly.category is category
    assert friendly.title == title
    assert friendly.original_error == message


def test_status_code_wins_over_body_code() -> None:
    """The HTTP status is checked before the JSON error code."""
    friendly = classify_error(
        Exception('Expected status code \'200\' but received \'503\': {"code":5005}')
    )
    assert friendly.title == "Service Unavailable"


def test_unknown_code_falls_through_to_patterns() -> None:
    """A code without a mapping still lets the message patterns match."""
    friendly = classify_error(Exception('{"code":9999,"message":"timeout"}'))
    assert friendly.category is ErrorCategory.NETWORK


@pytest.mark.parametrize(
    ("status", "category", "title"),
    [
        (404, ErrorCategory.CLIENT_ERROR, "Device Not Found"),
        (418, ErrorCategory.CLIENT_ERROR, "Client Error (418)"),
        (507, ErrorCategory.SERVER_ERROR, "Server Error (507)"),
    ],
)
def test_classify_client_response_error(
    status: int, category: ErrorCategory, title: str
) -> None:
    """aiohttp response errors are classified by their status."""
    friendly = classify_error(response_error(status))

    assert friendly.category is category
    assert friendly.title == title


def test_unknown_error() -> None:
    """Anything unrecognised becomes an unknown error that quotes the message."""
    friendly = classify_error(ValueError("something odd"))

    assert friendly.category is ErrorCategory.UNKNOWN
    assert "something odd" in friendly.message
    assert not friendly.is_recoverable
    assert not friendly.is_persistent


def test_known_errors_are_not_mutated() -> None:
    """Classifying copies the shared error instead of changing it."""
    first = classify_error(Exception("received '500' first"))
    second = classify_error(Exception("received '500' second"))

    assert first.original_error == "received '500' first"
    assert second.original_error == "received '500' second"


@pytest.mark.parametrize(
    ("category", "recoverable", "persistent"),
    [
        (ErrorCategory.ADAPTER_COMMUNICATION, True, False),
        (ErrorCategory.NETWORK, True, False),
        (ErrorCategory.RATE_LIMIT, True, False),
        (ErrorCategory.SERVER_ERROR, True, False),
        (ErrorCategory.AUTHENTICATION, False, True),
        (ErrorCategory.CLIENT_ERROR, False, True),
        (ErrorCategory.UNKNOWN, False, False),
    ],
)
def test_recoverable_and_persistent(
    category: ErrorCategory, recoverable: bool, persistent: bool
) -> None:
    """Each category is either self-healing, needs the user, or neither."""
    from custom_components.panasonic_cc.error_handler import FriendlyError

    friendly = FriendlyError(category=category, title="t", message="m")

    assert friendly.is_recoverable is recoverable
    assert friendly.is_persistent is persistent


def test_command_failure_names_device_and_action() -> None:
    """Adapter errors during a command mention the device and the action."""
    err = Exception('{"code":5005}')
    friendly = friendly_error_for_command_failure("Set Temperature", "Living room", err)

    assert friendly.category is ErrorCategory.ADAPTER_COMMUNICATION
    assert "'Living room'" in friendly.message
    assert "set temperature" in friendly.message
    assert friendly.original_error == str(err)


def test_command_failure_passes_other_errors_through() -> None:
    """Non-adapter errors keep the plain classification."""
    err = Exception("received '401'")

    assert friendly_error_for_command_failure("Turn on", "AC", err) == classify_error(err)
