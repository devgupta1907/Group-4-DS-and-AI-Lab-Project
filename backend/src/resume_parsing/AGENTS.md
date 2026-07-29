# AGENTS.md — Resume Parsing module

Scope: everything under `src/resume_parsing/`. These rules apply to this module
only. They are not suggestions — three independent mechanisms fail the build
when one is broken (see **Enforcement**).

If you are here to add or change something, read *The three rules* and *Adding a
capability* first. They answer most questions.

---

## What this module is

It turns one uploaded file into one validated **Candidate Profile**, and
publishes nothing else. It is the entry point of the whole pipeline; Career
Recommendation and Job Matching consume its output and never its internals.

```
upload → route → preprocess → extract → merge/normalise → validate
                                              ↓ fails
                                          repair (Gemini Flash)
                                              ↓
                                     persist (encrypted) → SSE to client
```

---

## The three rules

### 1. All logic lives in `internal/`

Pipeline stages, provider clients, ORM models, the repository, crypto — all of
it is under `internal/`. Nothing outside `src/resume_parsing/` may import from
it, and inside the module only `dependencies.py` may.

*Why:* it makes the module's public surface small enough to keep honest. If the
only importable things are `service.py` and `schemas.py`, then those are the
only things that can be depended on, and everything else stays free to change.

### 2. `service.py` is the single contract

`service.py` declares `ResumeParsingService` — the complete set of operations
the routing layer may request — plus `UploadedResume`. It is the only file in
this module `router.py` imports for *behaviour*.

*Why:* one file answers "what can this module do?" without reading an
implementation. It is also the seam a test doubles at, which is why the SSE
tests need no database and no API key.

**If a route needs something the contract does not offer, extend the contract.
Never reach past it.**

### 3. Routers never touch the database

`router.py` must not import `sqlalchemy`, `asyncpg`, `src.core.db`, the
repository, or any ORM model. It receives a built service through
`dependencies.py` and awaits it.

*Why:* the moment a route can issue a query, ownership checks start living in
routes, and the answer to "can this user see this row?" stops having one place
to look. That answer lives in `internal/repository.py` and nowhere else.

---

## Layering

```
router.py          transport + serialisation. Decides nothing.
   ↓
dependencies.py    composition root. The only non-internal file that may
                   name an infrastructure type (AsyncSession) or build
                   internals — that is its whole job.
   ↓
internal/          everything real.
   ↓
service.py         the contract. Protocol + DTOs. Depends on nothing.
```

Imports only ever point downward. There is no upward import anywhere, including
"just for a type".

`service.py` sits at the *bottom*, not the middle: the router calls it and
`internal/` implements it, so both point at it and it points at nothing. That
inversion is what lets `test_router_sse.py` double the whole module with a
40-line stub and no database.

---

## Adding a capability

Always in this order. Skipping a step is how a layer gets bypassed.

1. **Declare** the method on `ResumeParsingService` in `service.py`, with a
   docstring stating what it raises.
2. **Implement** it on `ResumeParsingServiceImpl` in `internal/service_impl.py`.
3. **Persist** through `internal/repository.py` if it needs data — add the query
   there, with the `user_id` filter in the same statement.
4. **Wire** it in `dependencies.py` if construction changes.
5. **Expose** it in `router.py`.

---

## Rules that are not about layering

**File size.** No file over ~250 lines. `router.py` stays under 100 — if it
grows, logic has leaked into it.

**Pipeline stages are pure functions** over `internal/domain.py` values. No I/O,
no session, no provider call inside `routing.py`, `preprocess.py`,
`postprocess.py` or `validation.py`. Orchestration and I/O belong to
`service_impl.py`. This is what makes those stages testable without fixtures.

**`parse()` never raises for an expected failure.** By the time the first event
is yielded the response is already a committed 200 with an open stream; a raised
exception reaches the browser as a truncated stream with no explanation. Yield
an `ErrorEvent` instead. Add new failure modes to `errors.py` with a stable
`code` — the UI branches on codes, never on message text.

**No module may import another module.** `resume_parsing` does not import
`career_recommendation` and vice versa. Shared needs go through `src/core/`, and
only if they are genuinely application-level.

---

## PII contract

Non-negotiable, from the security architecture.

**Never in the schema:** email, phone, date of birth, gender, marital status,
nationality, parent's or spouse's name, photograph, government identifiers.
`parsed_resume_schema.json` sets `additionalProperties: false`, so a model that
transcribes an email produces an *invalid* profile and is rejected at the
validation gate. The prompt asks; the validator enforces. Do not relax
`additionalProperties` — that is the enforcement, not a style choice.

**Retained but encrypted:** name, location, employer, institution, dates, links.
Sealed as one Fernet ciphertext in `internal/crypto.py`, opened only for the
authenticated owner.

**Transient:** the uploaded bytes and rendered page images. They exist inside one
request and are released in a `finally` block. Never write them to disk, never
store them in a table, never attach them to a log record.

**Logging:** log that something happened, never what was in it. No resume text,
no profile JSON, no raw model response — not even at DEBUG. `internal/repository.audit`
is the sanctioned trail; it records actor, action, outcome and nothing else.

---

## Model contract

**Prompt changes are production changes.** `internal/prompts/system.py` is the
module's entire adaptation strategy — no weights are trained. Tune on the
34-resume dev set; never on the 52-resume held-out test set.

**The document is data, not instruction.** Resume content always travels as its
own content part, never concatenated into the instruction string. Rule 7 of the
system prompt states that document text cannot override the rules. If you change
how content is assembled, preserve that separation.

**Fallback is strictly a repair path.** Gemma and Gemini Flash never run
together and never vote. Flash is reached only after the primary output fails
the validation gate. This is a cost and latency bound, not a quality trick — do
not turn it into an ensemble.

**Absence is a valid state.** A fresher has no experience; most resumes have no
projects. Never force-fill a section and never treat an empty one as failure.
Low coverage decides whether repair runs; it does not decide validity.

**Partial beats nothing.** If both models fail the gate, persist the best result
with `needs_review` flags rather than discarding it.

---

## Running it locally

```bash
cd backend
docker compose up -d                  # Postgres 16
uv sync
cp .env.example .env                  # then fill in the two keys below
uv run python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
#   -> PROFILE_ENCRYPTION_KEY
#   -> GOOGLE_AI_STUDIO_API_KEY from https://aistudio.google.com/apikey
uv run alembic upgrade head
uv run uvicorn src.app:create_app --factory --reload
```

Then `cd frontend && npm install && npm run dev` and open http://localhost:5173.

`RESUME_PRIMARY_MODEL` must be the exact Gemma model id your AI Studio project
exposes. It is configuration, not code, precisely because that id changes.

Without `GOOGLE_AI_STUDIO_API_KEY` the read routes still work; an upload streams
a `provider_not_configured` error frame instead of a profile.

---

## Enforcement

| Mechanism | Runs with | Catches |
|---|---|---|
| `tests/resume_parsing/test_architecture.py` | `pytest` | router→internal/DB imports, internals leaking out, I/O inside pipeline stages, PII field names in the schema |
| `.importlinter` | `lint-imports` | full import graph: layering, module isolation, SQL confined to the repository |
| `ruff` | `ruff check` | relative-import escapes out of the package |

Run all three before pushing:

```bash
uv run pytest tests/resume_parsing -v
uv run lint-imports
uv run ruff check src/resume_parsing
```

To see them work, add `from src.resume_parsing.internal.repository import ResumeParsingRepository`
to `router.py`. Both the test and `lint-imports` fail. That is the point.
