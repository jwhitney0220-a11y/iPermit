"""Email-sender seam (S07-02, SAAS-07).

The first SaaS flow that needs an email channel is the team-invite path: a
team admin invites an unregistered colleague, the platform sends them a link
carrying a single-use, time-bounded acceptance token (see ``routers/team.py``
and ``routers/invitations.py``). The token round-trips through email — never
the API — so a database read alone cannot impersonate the invitee.

The :class:`EmailSender` protocol is the swap point. The default
:class:`LocalEmailSender` captures messages in process memory so tests can
assert on subject/body without an SMTP service; staging/production substitute
a real provider (SES, SendGrid, raw SMTP) behind the same protocol via
``get_email_sender()``. Production providers are stubbed here — they fail
fast with a clear error so a non-local env is forced to wire a real provider
rather than silently dropping mail.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from .settings import Settings, get_settings


@dataclass(frozen=True)
class EmailMessage:
    """One outbound email. Plain-text body keeps the surface trivial."""

    to: str
    subject: str
    body: str
    category: str = "transactional"


class EmailSender(Protocol):
    """The minimum send surface; providers slot in behind this seam."""

    def send(self, message: EmailMessage) -> None:
        """Deliver *message*. Raises on transport failure."""


@dataclass
class LocalEmailSender:
    """In-process capture used by tests + local dev (no SMTP I/O)."""

    sent: list[EmailMessage] = field(default_factory=list)

    def send(self, message: EmailMessage) -> None:
        """Append *message* to :attr:`sent` so tests can assert on it."""
        self.sent.append(message)


class _UnconfiguredEmailSender:
    """Default for staging/prod when no provider is wired — fail loudly."""

    def send(self, message: EmailMessage) -> None:
        """Raise so silent mail-drops cannot happen in staging/production."""
        raise RuntimeError(
            "Email provider not configured. Set EMAIL_PROVIDER and the matching "
            f"provider settings (refused send to {message.to})."
        )


_LOCAL_SENDER = LocalEmailSender()


def get_email_sender(settings: Settings | None = None) -> EmailSender:
    """Return the configured :class:`EmailSender` for the active environment.

    ``EMAIL_PROVIDER=local`` (the default) yields the in-process capture used
    by tests and the dev container. Any other value with no provider wired up
    yields the fail-fast sender so a misconfigured non-local deploy raises
    instead of silently dropping mail.
    """
    settings = settings or get_settings()
    if settings.email_provider == "local":
        return _LOCAL_SENDER
    return _UnconfiguredEmailSender()


def get_local_sender() -> LocalEmailSender:
    """Return the module-level local capture (tests inspect ``.sent``)."""
    return _LOCAL_SENDER


__all__ = [
    "EmailMessage",
    "EmailSender",
    "LocalEmailSender",
    "get_email_sender",
    "get_local_sender",
]
