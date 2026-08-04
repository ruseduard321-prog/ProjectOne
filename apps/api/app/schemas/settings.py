"""Request and response contracts for the profile settings endpoint.

Deliberately small. [[STEP-19 Settings and BYOK UI]] task 4 says to *reuse what
STEP-13 built where it exists, and add only what the screens genuinely need* --
so workspace renaming reuses `WorkspaceRenameRequest`, the profile read reuses
`ProfileResponse`, and the one genuine gap is here: nothing could previously
change a display name.

`email` is **not** editable through this module, and that is a decision rather
than an omission. The address is authoritative in Supabase Auth and reconciled
into `public.users` on every authenticated request
(`UserRepository.ensure_profile`), so a write here would be overwritten on the
user's next request -- a settings field that silently reverts is worse than one
that is honestly absent. Changing an address means changing it upstream, which
needs a verification flow that does not exist yet and is not this step's scope.
"""

from typing import Annotated

from pydantic import BaseModel, StringConstraints

#: A user's chosen display name.
#:
#: Stripped before the bound is applied, so a whitespace-only submission is
#: rejected rather than rendering as a blank name beside every action the user
#: takes -- the same reasoning as `WorkspaceName`.
DisplayName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=120),
]


class ProfileUpdateRequest(BaseModel):
    """A change to the caller's own display name.

    Carries no `id`. The row updated is always the verified caller's, taken from
    the token -- an id field here would be an impersonation parameter, and the
    `users_update_self` policy would refuse it anyway by matching zero rows,
    which is a 404 where a 403 belongs.
    """

    display_name: DisplayName
