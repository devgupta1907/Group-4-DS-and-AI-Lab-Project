"""★ THE CONTRACT FILE ★

This is the *only* file in this module that `router.py` is allowed to import
for behaviour (alongside `schemas.py` and `errors.py` for shapes). It declares
what the routing layer may ask the module to do, and nothing about how any of
it happens.

Adding a capability follows one order, always:

    1. declare the method here,
    2. implement it in `internal/service_impl.py`,
    3. wire it in `dependencies.py`,
    4. expose it in `router.py`.

If a route needs something this file does not offer, the fix is to extend this
file — never to reach past it into `internal/`.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Protocol, runtime_checkable
from uuid import UUID

from src.core.security import CurrentUser
from src.resume_parsing.schemas import CandidateProfile, ParseEvent, ProfileRecord, ProfileSummary


@dataclass(frozen=True, slots=True)
class UploadedResume:
    """A file handed to the module, already read into memory by the router.

    The router does not interpret these bytes; it only carries them across the
    boundary. Size and page limits are enforced inside the module so the rules
    live in one place.
    """

    filename: str
    content_type: str | None
    content: bytes


@runtime_checkable
class ResumeParsingService(Protocol):
    """Everything the routing layer may ask of this module."""

    def parse(
        self, upload: UploadedResume, user: CurrentUser
    ) -> AsyncIterator[ParseEvent]:
        """Run the parse pipeline, yielding progress events as they happen.

        Yields `StageEvent`s throughout, then exactly one terminal event:
        `ProfileEvent` on success or `ErrorEvent` on failure. The router turns
        each event into one SSE frame and does nothing else.

        Implementations must not raise for expected failures — they yield an
        `ErrorEvent` instead, because an SSE response has already begun and its
        status code can no longer be changed.
        """
        ...

    async def get_profile(self, profile_id: UUID, user: CurrentUser) -> ProfileRecord:
        """Return one profile owned by `user`.

        Raises `ProfileNotFound` when it does not exist *or* is owned by someone
        else — the two cases are deliberately indistinguishable to the caller.
        """
        ...

    async def submit_manual_profile(
        self, profile: CandidateProfile, user: CurrentUser
    ) -> ProfileRecord:
        """Persists a profile the candidate typed in directly, bypassing
        upload and extraction entirely.

        Returns the same `ProfileRecord` shape a completed parse produces —
        `route` is `"manual"`, so downstream consumers and the UI can still
        tell the two apart, but nothing about the shape itself differs.

        Raises `EmptyManualProfile` if the profile carries no usable signal
        (see `CandidateProfile.has_usable_signal`) — there has to be
        something for career recommendation or job discovery to match
        against.
        """
        ...

    async def update_profile(
        self, profile_id: UUID, user: CurrentUser, profile: CandidateProfile
    ) -> ProfileRecord:
        """Overwrite the stored profile with candidate-edited content (e.g.
        adding a location the extractor missed, fixing a misparsed skill)
        before career recommendation or job discovery runs against it.

        Takes and returns the FULL `CandidateProfile` shape — same as
        `ProfileRecord.profile` from `get_profile` — not a partial patch;
        the caller is expected to have started from a `get_profile()`
        result and edited fields on it. Raises `ProfileNotFound` under the
        same rule as `get_profile`.
        """
        ...

    async def list_profiles(self, user: CurrentUser) -> list[ProfileSummary]:
        """Summaries of every profile owned by `user`, newest first."""
        ...

    async def delete_profile(self, profile_id: UUID, user: CurrentUser) -> None:
        """Erase a profile and its parse job (DPDP Act erasure right).

        Raises `ProfileNotFound` if the user does not own it.
        """
        ...
