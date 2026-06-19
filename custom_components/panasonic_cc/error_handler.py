"""Error classification and user-friendly error handling for Panasonic CC."""
from __future__ import annotations

import dataclasses
import logging
import re
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any

from aiohttp import ClientResponseError

_LOGGER = logging.getLogger(__name__)


class ErrorCategory(Enum):
    """Categories of errors that can occur with the Panasonic API."""
    # Communication between Panasonic servers and the device
    ADAPTER_COMMUNICATION = auto()
    # Authentication / authorization issues
    AUTHENTICATION = auto()
    # Network connectivity issues (timeouts, DNS, etc.)
    NETWORK = auto()
    # Rate limiting from the API
    RATE_LIMIT = auto()
    # Server-side errors (5xx)
    SERVER_ERROR = auto()
    # Invalid request / bad parameters (4xx)
    CLIENT_ERROR = auto()
    # Unknown / unclassified errors
    UNKNOWN = auto()


@dataclass(frozen=True)
class FriendlyError:
    """A user-friendly representation of an error."""
    category: ErrorCategory
    title: str
    message: str
    suggestion: str | None = None
    original_error: str = ""

    @property
    def is_recoverable(self) -> bool:
        """Whether the error is likely to resolve on its own."""
        return self.category in (
            ErrorCategory.ADAPTER_COMMUNICATION,
            ErrorCategory.NETWORK,
            ErrorCategory.RATE_LIMIT,
            ErrorCategory.SERVER_ERROR,
        )

    @property
    def is_persistent(self) -> bool:
        """Whether the error likely requires user action."""
        return self.category in (
            ErrorCategory.AUTHENTICATION,
            ErrorCategory.CLIENT_ERROR,
        )


# Mapping of known API error codes to friendly errors
KNOWN_ERROR_CODES = {
    5005: FriendlyError(
        category=ErrorCategory.ADAPTER_COMMUNICATION,
        title="Device Communication Error",
        message="The Panasonic server could not reach your air conditioner. The device may be offline, disconnected from the network, or the Panasonic cloud service is having trouble communicating with it.",
        suggestion="Check that your AC unit is powered on and connected to the internet. If the problem persists, try restarting the AC unit or check the Panasonic app to see if the device is reachable there.",
    ),
    5001: FriendlyError(
        category=ErrorCategory.ADAPTER_COMMUNICATION,
        title="Device Not Responding",
        message="Your air conditioner is not responding to commands. It may be offline or unreachable.",
        suggestion="Verify the AC unit is powered on and has internet connectivity. Try controlling it from the Panasonic app to confirm.",
    ),
    429: FriendlyError(
        category=ErrorCategory.RATE_LIMIT,
        title="Rate Limited",
        message="Too many requests have been sent to the Panasonic API. The server is temporarily rejecting requests.",
        suggestion="This should resolve automatically. The integration will wait before retrying.",
    ),
    401: FriendlyError(
        category=ErrorCategory.AUTHENTICATION,
        title="Authentication Failed",
        message="The integration could not authenticate with the Panasonic service. Your credentials may have expired or been invalidated.",
        suggestion="Remove and re-add the integration to re-authenticate.",
    ),
    403: FriendlyError(
        category=ErrorCategory.AUTHENTICATION,
        title="Access Denied",
        message="The integration does not have permission to access the requested resource.",
        suggestion="Check that your account has access to this device in the Panasonic app.",
    ),
    404: FriendlyError(
        category=ErrorCategory.CLIENT_ERROR,
        title="Device Not Found",
        message="The requested device was not found. It may have been removed from your account.",
        suggestion="Verify the device still exists in your Panasonic account.",
    ),
    500: FriendlyError(
        category=ErrorCategory.SERVER_ERROR,
        title="Server Error",
        message="The Panasonic server returned an internal error. This is a temporary issue on the server side.",
        suggestion="This should resolve automatically. If it persists, check the Panasonic service status.",
    ),
    502: FriendlyError(
        category=ErrorCategory.SERVER_ERROR,
        title="Bad Gateway",
        message="The Panasonic server received an invalid response from an upstream server.",
        suggestion="This is a temporary server issue. It should resolve automatically.",
    ),
    503: FriendlyError(
        category=ErrorCategory.SERVER_ERROR,
        title="Service Unavailable",
        message="The Panasonic service is temporarily unavailable, possibly due to maintenance or overload.",
        suggestion="This should resolve automatically. Check the Panasonic service status if it persists.",
    ),
    504: FriendlyError(
        category=ErrorCategory.SERVER_ERROR,
        title="Gateway Timeout",
        message="The Panasonic server timed out waiting for a response from an upstream service.",
        suggestion="This is a temporary issue. It should resolve automatically.",
    ),
}

# Regex patterns for error message matching (fallback when no code is found)
ERROR_PATTERNS = [
    (
        re.compile(r"adapter\s+communication\s+error", re.IGNORECASE),
        FriendlyError(
            category=ErrorCategory.ADAPTER_COMMUNICATION,
            title="Device Communication Error",
            message="The Panasonic server could not reach your air conditioner. The device may be offline or disconnected from the network.",
            suggestion="Check that your AC unit is powered on and connected to the internet. Try controlling it from the Panasonic app to confirm.",
        ),
    ),
    (
        re.compile(r"device\s+(not\s+)?respond(ing|ed)?", re.IGNORECASE),
        FriendlyError(
            category=ErrorCategory.ADAPTER_COMMUNICATION,
            title="Device Not Responding",
            message="Your air conditioner is not responding to commands.",
            suggestion="Verify the AC unit is powered on and has internet connectivity.",
        ),
    ),
    (
        re.compile(r"timeout|timed?\s*out", re.IGNORECASE),
        FriendlyError(
            category=ErrorCategory.NETWORK,
            title="Connection Timeout",
            message="The request to the Panasonic service timed out. This could be a network issue or the service being slow.",
            suggestion="Check your internet connection. If the problem persists, the Panasonic service may be experiencing issues.",
        ),
    ),
    (
        re.compile(r"unauthorized|authentication|invalid\s+(token|session|credentials)", re.IGNORECASE),
        FriendlyError(
            category=ErrorCategory.AUTHENTICATION,
            title="Authentication Error",
            message="The integration could not authenticate with the Panasonic service.",
            suggestion="Remove and re-add the integration to re-authenticate.",
        ),
    ),
    (
        re.compile(r"rate\s+limit|too\s+many\s+requests", re.IGNORECASE),
        FriendlyError(
            category=ErrorCategory.RATE_LIMIT,
            title="Rate Limited",
            message="Too many requests have been sent to the Panasonic API.",
            suggestion="This should resolve automatically. The integration will wait before retrying.",
        ),
    ),
    (
        re.compile(r"service\s+unavailable|maintenance", re.IGNORECASE),
        FriendlyError(
            category=ErrorCategory.SERVER_ERROR,
            title="Service Unavailable",
            message="The Panasonic service is temporarily unavailable.",
            suggestion="This should resolve automatically. Check the Panasonic service status if it persists.",
        ),
    ),
]


def classify_error(err: Exception) -> FriendlyError:
    """Classify an exception into a user-friendly error.

    This function attempts to extract error codes and messages from the
    exception and map them to a known friendly error. If no match is found,
    it falls back to pattern matching on the error string, and finally
    returns a generic unknown error.
    """
    error_str = str(err)

    # Check for HTTP status code in the error string
    # Pattern: "Expected status code '200' but received '500'"
    status_match = re.search(r"received\s+['\"]?(\d{3})['\"]?", error_str)
    if status_match:
        status_code = int(status_match.group(1))
        if status_code in KNOWN_ERROR_CODES:
            return dataclasses.replace(KNOWN_ERROR_CODES[status_code], original_error=error_str)

    # Check for JSON error code in response body
    # Pattern: {"code":5005,"message":"Adapter Communication error"}
    code_match = re.search(r'"code"\s*:\s*(\d+)', error_str)
    if code_match:
        error_code = int(code_match.group(1))
        if error_code in KNOWN_ERROR_CODES:
            return dataclasses.replace(KNOWN_ERROR_CODES[error_code], original_error=error_str)

    # Check for HTTP status code patterns (401, 403, 404, 429, 500, etc.)
    http_code_match = re.search(r"\b(4\d{2}|5\d{2})\b", error_str)
    if http_code_match:
        http_code = int(http_code_match.group(1))
        if http_code in KNOWN_ERROR_CODES:
            return dataclasses.replace(KNOWN_ERROR_CODES[http_code], original_error=error_str)

    # Try pattern matching on error message
    for pattern, friendly in ERROR_PATTERNS:
        if pattern.search(error_str):
            return dataclasses.replace(friendly, original_error=error_str)

    # Check for ClientResponseError
    if isinstance(err, ClientResponseError):
        status = err.status
        if status in KNOWN_ERROR_CODES:
            return dataclasses.replace(KNOWN_ERROR_CODES[status], original_error=error_str)
        if 400 <= status < 500:
            return FriendlyError(
                category=ErrorCategory.CLIENT_ERROR,
                title=f"Client Error ({status})",
                message=f"The request to the Panasonic service was rejected with status {status}.",
                suggestion="This may be a temporary issue. If it persists, check the Panasonic app for device status.",
                original_error=error_str,
            )
        if 500 <= status < 600:
            return FriendlyError(
                category=ErrorCategory.SERVER_ERROR,
                title=f"Server Error ({status})",
                message=f"The Panasonic server returned an error (status {status}).",
                suggestion="This is likely a temporary issue on the server side. It should resolve automatically.",
                original_error=error_str,
            )

    # Generic fallback
    return FriendlyError(
        category=ErrorCategory.UNKNOWN,
        title="Unknown Error",
        message=f"An unexpected error occurred while communicating with the Panasonic service: {error_str}",
        suggestion="If this persists, please report the issue on the integration's GitHub page.",
        original_error=error_str,
    )


def friendly_error_for_command_failure(
    action: str,
    device_name: str,
    err: Exception,
) -> FriendlyError:
    """Create a friendly error for a command/action failure on a device.

    Wraps the classified error with context about what action was being performed.
    """
    base = classify_error(err)

    # For adapter communication errors during commands, provide more specific messaging
    if base.category == ErrorCategory.ADAPTER_COMMUNICATION:
        return FriendlyError(
            category=ErrorCategory.ADAPTER_COMMUNICATION,
            title="Device Communication Error",
            message=f"The Panasonic server could not reach '{device_name}' while trying to {action.lower()}. The device may be offline, disconnected from the network, or the cloud service is having trouble communicating with it.",
            suggestion="Check that your AC unit is powered on and connected to the internet. Try controlling it from the Panasonic app to confirm. If the device works in the app, this may be a temporary issue.",
            original_error=str(err),
        )

    return base
