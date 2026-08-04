"""Authentication port.

Every record in the system is owned by a `user_id`. Routes depend on
`CurrentUser`, never on how it was obtained, so swapping the dev resolver for
Google SSO later touches this file and nothing else.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header
from pydantic import BaseModel

from src.core.config import get_settings


class CurrentUser(BaseModel):
    """The authenticated owner of the records a request touches."""

    id: str
    email: str


async def get_current_user(
    x_dev_user_id: Annotated[str | None, Header(alias="X-Dev-User-Id")] = None,
    x_dev_user_email: Annotated[str | None, Header(alias="X-Dev-User-Email")] = None,
) -> CurrentUser:
    """Dev resolver: trusts a header, falling back to the configured dev user.

    This is deliberately trivial. It exists so that ownership is threaded
    through the whole module from day one; replacing it with a Google SSO token
    verifier requires no change to any router, service or repository.
    """
    settings = get_settings()
    return CurrentUser(
        id=x_dev_user_id or settings.dev_user_id,
        email=x_dev_user_email or settings.dev_user_email,
    )


CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user)]
