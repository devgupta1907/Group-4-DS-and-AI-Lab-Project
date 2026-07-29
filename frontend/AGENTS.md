# AGENTS.md — Frontend

Scope: everything under `frontend/`. Each rule below is enforced by
`eslint.config.js`, so `npm run lint` is the arbiter, not review.

---

## Structure

```
src/
  main.tsx, App.tsx          the shell. Mounts features. Contains no feature logic.
  shared/                    used by every feature, knows about none of them
    api/                     the ONLY place that touches the network
    ui/                      presentational primitives
    styles/                  design tokens + global reset
    utils/                   pure helpers
  features/<feature>/        one self-contained vertical slice
    types/                   the backend contract, mirrored
    api/                     this feature's endpoints
    hooks/                   all state and orchestration
    components/              presentation, driven by hooks
    pages/                   composition of the above
    constants.ts
    index.ts                 the feature's public surface
```

Dependencies point **inward and downward**: `pages → components → hooks → api →
shared`. Never the reverse.

---

## The rules

### 1. Only `api/` touches the network

`fetch`, `XMLHttpRequest` and `EventSource` are banned everywhere except
`shared/api/**` and `features/*/api/**`.

*Why:* auth headers, base URLs and error decoding then have exactly one
definition. When Google SSO lands, `shared/api/httpClient.ts` changes and no
component notices.

### 2. Components consume hooks; they never orchestrate requests

A component may not import an `api/` module at all. It renders what a hook
returns.

*Why:* a component that fetches also owns loading state, cancellation and race
conditions — and it re-implements them each time. Put that in a hook once and
the component becomes a pure function of its props.

Concretely: `useResumeUpload` owns the SSE stream, the abort controller, the
stage timeline and the terminal result. `ResumeUploadPanel` renders that object
and knows nothing about streams.

### 3. Derived state belongs in a hook, not in JSX

If a value needs a conditional, a loop, or more than one operator to compute,
it is derived state. `useParseProgress` exists because mapping a stage timeline
onto per-step visual states is a small state machine, and a small state machine
inside JSX is unreadable and untestable.

### 4. No `any`

The parsed-profile contract in `features/resume-parsing/types/parsedProfile.ts`
mirrors the backend schema exactly. `any` anywhere in the chain makes that
mirror decorative. Narrow unknown values explicitly — `toApiError` in
`shared/api/ApiError.ts` is the pattern.

### 5. Small files, small functions

| Limit | Applies to |
|---|---|
| 150 lines | components (`features/*/components/**`, `shared/ui/**`) |
| 200 lines | everything else |
| 80 lines | any single function |
| complexity 12 | any single function |

A component over the limit is doing more than one thing. Split by
responsibility, not by line count: `ProfileView` composes seven section
components rather than rendering seven sections itself.

### 6. Feature isolation

- `shared/` must not import from `features/` — ever.
- One feature must not import another. Cross-feature needs go through `shared/`,
  or the code is not actually shared.
- `shared/ui` primitives are feature-agnostic. If a component needs to know what
  a resume is, it belongs in `features/resume-parsing/components/`.

*Why:* the modules in this project are owned by different people. A frontend
import graph that mirrors the backend's module boundaries is what keeps a change
to Resume Parsing from breaking Career Recommendation.

### 7. Styling comes from tokens

CSS Modules only, co-located as `Component.module.css`. Every colour, space,
radius, font size and shadow comes from `shared/styles/tokens.css`. No hardcoded
hex values in a component stylesheet.

*Why:* dark mode works because there is exactly one definition of `--c-surface`.
One hardcoded `#fff` and a card goes white in dark mode.

### 8. Reuse before you add

Before writing a component, check `shared/ui/`. If you write the same thing
twice, move it there on the second occurrence. `EntryCard` exists because
experience, education, projects and certifications are all "a repeated entry
with a heading, a subheading and some metadata" — one component, four uses.

---

## Product rules specific to Resume Parsing

**An empty section is shown, not hidden.** `SectionShell` renders an explicit
"No projects on this resume" state. A section that vanishes reads as the parser
having failed; a section that says it found nothing reads as the truth. Only 5
of 86 gold-set resumes have projects — empty is normal.

**Never display or request email or phone.** They are excluded at the backend
schema level, so they cannot arrive. Do not add fields for them, and do not add
a "contact the candidate" affordance that implies they exist.

**Branch on error `code`, never on message text.** The backend gives every
failure a stable code (`unsupported_file_type`, `file_too_large`,
`provider_not_configured`, …). Messages are wording and will change.

**Client-side validation is a courtesy, not a control.** `useFileValidation`
mirrors the server's limits so a 20 MB file fails instantly instead of after a
20 MB upload. The server re-checks everything regardless.

**SSE is read through `fetch`, not `EventSource`.** The upload is a multipart
POST and `EventSource` only does GET. `shared/api/sseClient.ts` parses frames
off the response body. Do not "simplify" it to `EventSource` — it cannot work.

---

## Before pushing

```bash
npm run lint        # rules 1–7
npm run typecheck   # rule 4, and the backend contract
npm run build
```

To see the rules bite, put `fetch('/api/whatever')` inside a component. Lint
fails with the rule number and what to do instead.
