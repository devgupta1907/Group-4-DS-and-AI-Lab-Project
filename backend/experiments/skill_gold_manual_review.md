# Manual Skill Gold Review — Five-Resume Evidence Pack

## Purpose

This review checks whether low skill-extraction scores arise from the model, the
gold annotation, or a mismatch in how phrases are divided into atomic skills.
For each resume, the evidence pack contains the original PDF, the current gold
skills, and the predictions from Gemini prompt versions v006 and v007.

The source PDF is authoritative. Gold must not be changed merely to resemble a
model prediction. A correction is justified only when the PDF visibly supports
it and the same annotation policy can be applied consistently to every resume.

## Review labels

- **Gold omission:** a source-supported skill is missing from gold.
- **Model omission:** a gold skill is visibly present but absent from prediction.
- **Model over-extraction:** a duty, adjective, objective, or unrelated prose was
  returned as a skill.
- **Boundary/canonicalization mismatch:** both sides identify the concept but
  divide or name it differently.
- **Policy decision:** the source is clear, but the dataset contract must decide
  whether that category belongs in `skills`.

## Five selected resumes

### 1. accountant__44

Why selected: it has a large printed skills area and produces many disagreements,
making it useful for detecting incomplete gold and excessive model extraction.

Preliminary observation: the current gold contains canonical accounting tools
and competencies, whereas v007 additionally returns visible soft-skill phrases
and several software/product variants. Each disagreement must be checked against
the PDF. A visibly printed item may be a gold omission; repeated product wording
or prose-like traits may instead require canonicalization or exclusion.

Reviewer decision:

- Confirm which returned items are visibly inside the skills area.
- Mark summary-only adjectives as out of scope unless the annotation policy
  explicitly includes summary competencies.
- Consolidate aliases only through the shared skill resolver, not by rewriting
  source meaning.

#### Source verification

The disputed values are present in the PDF, but in different document regions:

- `Governmental accounting` is supported by the professional-summary phrase
  `Knowledge in governmental accounting procedures`.
- `Accounts payable & receivable` is supported by the same summary, which says
  `accounts payables & receivables`. Accounts payable also appears repeatedly in
  work-history duties.
- Bookkeeping is explicitly visible. The upper skills area contains `Accounting
  & Bookkeeping Services`; the lower skills list contains `Advanced bookkeeping
  skills`, `Accounting and bookkeeping`, and `Creative Solutions Bookkeeping
  Software`.

Therefore, these are not fabricated concepts. However, the current gold is
internally inconsistent: it includes summary-derived governmental accounting and
accounts payable/receivable, but does not include the explicit bookkeeping
competencies from the printed skills list. It also canonicalizes several source
phrases without preserving an auditable raw phrase. This resume should not be
used to judge the model until the annotation scope is fixed. Under a
section-first policy, explicit bookkeeping entries should be represented and
summary-only concepts should be excluded unless duplicated in a skills section.
Under a whole-resume competency policy, all explicit competencies must be
annotated consistently rather than selectively.

### 2. accountant__fac6c23d5aafc14e

Why selected: v006 matched the six gold skills, while v007 added account
reconciliations, streamlining accounts, financial planning, and accounting.

Preliminary observation: OCR places these additional terms in the professional
summary, while the six gold values appear under `Key Skills`. This is primarily
a scope-policy example rather than an OCR failure. If the contract is
section-restricted, the additions are model over-extraction. If explicit summary
competencies are allowed, the gold is incomplete. The rule must be chosen once
and applied to all resumes.

Reviewer decision: choose whether explicit summary competencies are in scope.

### 3. advocate__3bbf2f150c0573b5

Why selected: v007 recovered all twelve current gold skills but also returned
English, Spanish, Excellent Researcher, Collaborative Leader, and Outstanding
Advocate.

Preliminary observation: English and Spanish visibly occur under a separate
Languages heading. Their mismatch is a policy problem: either languages belong
in `skills` everywhere or they need a separate field and must be excluded
everywhere. The three adjective-led phrases appear to be summary/profile
language and are likely over-extraction unless the PDF presents them as explicit
skill entries.

Reviewer decision:

- Decide whether languages belong in this schema's skill list.
- Reject flattering descriptors unless they are explicit competency entries.

### 4. advocate__ba77440de8f99831

Why selected: the PDF contains the phrase `Knowledge of Federal and State Laws`.
Gold represents this as `Federal Law` and `State Law`, while v007 retains the
combined source phrase.

Preliminary observation: this is a clear atomic-boundary mismatch, not an OCR
error. The preferred production representation is two independently matchable
legal competencies, but the transformation should be deterministic and shared
by gold preparation, scoring, and inference—not dependent on prompt obedience.

Reviewer decision: confirm the two-skill canonical representation.

### 5. agricultural__Image_70

Why selected: the PDF contains several coordinated or framed competency phrases,
including plant anatomy and transplant methods, budgeting and negotiating,
chemical application, mower operation, and leadership skills.

Preliminary observation: v007 improved recall for some concepts but over-split
`application of insecticide, fertilizers and fungicides` into unlike units and
split mower operation into bare tool names. It also returned rural-work ability,
agricultural technology, logistics, and product placement. This case shows both
boundary errors and possible over-extraction. The model generally reads the
words; the unresolved problem is deciding which spans are atomic competencies.

Reviewer decision:

- Keep `Plant anatomy` and `Plant transplant methods` separately.
- Keep chemical application as one competency unless the source independently
  claims expertise in each chemical.
- Keep mower operation as an operational skill rather than bare equipment names.
- Exclude duties or contextual abilities that are not reusable competencies.

## Report-ready finding

The five-resume audit demonstrates that low exact-match skill F1 is not caused by
one failure type. Some errors are genuine model omissions or over-extractions;
others arise because the model preserves a visible source phrase while the gold
uses a more atomic canonical form. Prompt v007 increased recall on the five
resumes from 0.6418 to 0.7164, but precision fell from 0.5811 to 0.5333, leaving
F1 nearly unchanged (0.6099 to 0.6115). This supports a two-stage design: first
extract source-supported skill phrases, then resolve them through a deterministic
or taxonomy-backed canonicalization layer. Manual gold corrections should be
made only after visual confirmation against the PDF and must follow the same
documented policy across the complete dataset.

## Review status

No gold records were changed during creation of this evidence pack. The five
cases are awaiting visual decisions, after which corrections can be applied as a
new versioned gold dataset while preserving the previous version as evidence.

## First accepted correction

`accountant__44` was subsequently corrected under `skill_sections_v001` after
visual review. Its gold skills now come only from explicit skill areas; summary
and work-history competencies are excluded. The original annotation remains
preserved, and the corrected view is produced by the versioned loader. This is
the first reviewed record, not evidence that the other 85 records have already
been manually verified under the new policy.
