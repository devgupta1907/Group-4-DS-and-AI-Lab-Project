# Vertex vision baseline notes

## Scoring configuration

The raw inference baseline remains preserved in the append-only ledger. Normalized comparison is a derived offline experiment over the same saved predictions, so it does not mutate raw evidence or make another model call. Each derived row references its source inference record and records the normalization version and source fingerprint.

The results-analysis notebook keeps automatic normalized derivation enabled. The runner is restart-safe: an inference record already scored with the same normalization fingerprint is skipped. When a new model or prompt experiment is added, running analysis automatically derives its normalized comparison. When the normalization implementation changes, its new source hash creates a separate experiment rather than overwriting earlier results.

## Raw schema adherence

In the first smoke-test responses, Gemma did not consistently adhere to the requested response schema. For example, several responses returned `name` and `location` at the root instead of under `contact`. This is tracked separately from final production-output accuracy through `raw_schema_valid` and `raw_schema_errors`.

The production postprocessor does not reinterpret unknown paths. A root-level `name` is therefore not treated as `contact.name`; it is absent from the final production profile. This is a schema-placement failure even when the extracted text itself is correct.

## Vertex MaaS structured-output correction

The original provider passed `response_schema` through the Google Gen AI SDK. Gemma MaaS returned JSON but did not consistently follow the schema. The final `v004` request uses two safeguards: Vertex's documented Pydantic `parse()` response format and `build_gemma_prompt()`, which places the complete JSON Schema directly in Gemma's user turn. System-role support is no longer treated as proof that schema-constrained decoding is active.

## Full baseline completion

- Source resumes: 86.
- Successful inference results: 84.
- Repeated timeout failures: `management__35` and `react_developer__176`.
- Successful coverage: 97.67%.
- Field metrics use the common cohort of 84 successful resumes.
- Operational failures are reported separately rather than converted into artificial field-level FN counts.

Both failed PDFs are valid but unusually tall, image-only, single-page documents. Their rendered dimensions and repeated 120-second timeouts indicate a long-page vision-processing limitation. Long-page tiling should be evaluated as a separate preprocessing experiment rather than silently applied to only these two baseline records.

## Location privacy decision

Exact candidate addresses are not needed for job matching. Production location output now retains locality only: city plus region/state and country when visible. Street, building, unit, floor, PO box and postal information is removed. The prompt, JSON Schema description, production postprocessor and Pydantic model all enforce the same policy.

The comparison evaluator applies the same production locality sanitizer to prediction and gold. Existing historical ledger evidence was not rewritten, because the ledger is append-only; future evidence rows store privacy-safe locations. Google Maps geocoding was rejected as the default because it would transmit exact addresses to another service, add policy/storage restrictions, latency and cost. If no city can be recovered safely, production stores `null` instead of guessing.

## Normalized comparison v001

Normalized v001 reused the 84 saved inference outputs and made zero additional LLM calls. Total local normalization time was approximately 0.096 seconds.

| Metric | Raw exact | Normalized v001 | Change |
|---|---:|---:|---:|
| Precision | 0.5230 | 0.5899 | +0.0668 |
| Recall | 0.5274 | 0.5961 | +0.0687 |
| Micro-F1 | 0.5252 | 0.5930 | +0.0677 |

Major F1 improvements were contact location `0.3759 -> 0.8205`, contact name `0.4684 -> 0.8101`, job titles `0.5995 -> 0.7851`, experience job title `0.6418 -> 0.8023`, and education institution `0.2682 -> 0.4022`. No field decreased. These are scoring-policy gains over the same model output, not improvements in model inference or latency.

## Experience error review

After v001, `experience.current_role` reached 0.9262 F1 and `experience.job_title` reached 0.8023. The weaker fields were company 0.5970, location 0.6728, start date 0.7100 and end date 0.7139.

Observed company problems included locations appended to company names, harmless punctuation differences, null-like placeholder strings, OCR spelling errors, missing employers and genuinely wrong employers. Observed date problems included complete ranges placed into one field, missing dates, placeholder strings and materially incorrect years. Dates must eventually be evaluated after pairing them with their corresponding job title/company; flattened date sets can credit a date attached to the wrong role.

## Normalized comparison v002 rules and result

Normalized v002 was appended for the same 84-resume cohort with zero LLM calls. It adds the following deterministic comparison rules, each displayed separately by the analysis notebook:

1. Normalize Unicode text to NFKC.
2. Compare text case-insensitively and collapse repeated whitespace.
3. Treat null-like placeholders as missing values.
4. Reduce locations to locality level and discard address/postal components.
5. Discard generic location placeholders such as `City, State` and `Location`.
6. Remove a company suffix only when it matches that experience entry's location.
7. Normalize punctuation for names, titles, organizations and certification text.
8. Treat ampersand and the word `and` equivalently in organization comparison.
9. Resolve only controlled degree abbreviations such as `B.Sc.` and `Bachelor of Science`.
10. Canonicalize common month/year spellings without inventing precision.
11. Split a visible date range into its start or end component for the corresponding field.

Company text is not truncated blindly at the first comma because legitimate company names in the evidence include `Google, Inc.`, `La Madeleine, Inc.`, `Marketing & Analytics, LLC`, and `Northstar, Inc.`. A location suffix is removed only when it matches the location from the same experience entry.

Fuzzy matching is not part of the official canonical TP/FP/FN score. A separate OCR-tolerant diagnostic metric may later be added for likely transcription errors, ideally constrained by a local city/state gazetteer. Dates, candidate names and company identities must not be automatically declared correct solely because their strings are similar.

### v002 measured improvement

- Micro-F1 increased from normalized v001 `0.5930` to v002 `0.6121` (`+0.0192`).
- Relative to the raw exact baseline `0.5252`, v002 improved Micro-F1 by `0.0869`.
- No evaluated field's F1 decreased.
- Contact aggregate F1 reached `0.8593`, above the initial `0.80` target.
- Experience aggregate F1 reached `0.7695`; its precision was `0.8193`, but recall was only `0.7254`.

Targeted field changes from normalized v001 to v002 were:

| Field | v001 F1 | v002 F1 | Change |
|---|---:|---:|---:|
| Contact location | 0.8205 | 0.8929 | +0.0724 |
| Experience company | 0.5970 | 0.6727 | +0.0757 |
| Experience start date | 0.7100 | 0.7713 | +0.0613 |
| Experience end date | 0.7139 | 0.7586 | +0.0447 |
| Certifications name | 0.4468 | 0.5435 | +0.0967 |
| Contact name | 0.8101 | 0.8354 | +0.0253 |
| Education institution | 0.4022 | 0.4246 | +0.0224 |

Experience remains below target mainly because recall is low: the model still omits companies, locations and dates or assigns them to the wrong experience entry. Normalization can fix representation and field-boundary artifacts, but it cannot recover information that was never extracted.

### Experiment identity bookkeeping

Two semantically identical v001 derived experiments were recorded because the original fingerprint included the offline orchestration module. A bookkeeping-only edit therefore changed the hash despite identical normalization behavior. Historical rows remain untouched as append-only evidence. Future derived experiment identity is based on the explicit normalization version and parent inference experiment; implementation hashes remain metadata. A normalization behavior change must increment the version, preventing orchestration-only changes from creating duplicate experiments.

## Skills and job-title diagnosis after v002

The combined Skills and job titles section scored `0.5002` F1, but the two fields have very different behavior:

| Field | TP | FP | FN | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|
| Skills | 504 | 723 | 503 | 0.4108 | 0.5005 | 0.4512 |
| Job titles | 149 | 38 | 41 | 0.7968 | 0.7842 | 0.7905 |

Skills contributed 1,226 FP/FN errors, while job titles contributed only 79. The combined section is therefore low primarily because of skills; job titles are only 0.0095 below the initial 0.80 target.

The main skills problems are:

1. The model converts complete responsibilities or requirements into skills. For example, long sentences about designing tests, evaluating compliance or leading programmes are returned as individual skill values.
2. Prediction and gold use different granularity. The model may split `Microsoft Word, Excel, Access, PowerPoint, Outlook` into atomic tools while gold stores one combined value, or may preserve a labelled group such as `Programming languages: Python, Groovy` while gold stores individual skills.
3. Equivalent technology names remain unmatched, such as `Cloud Formation` versus `CloudFormation`, `VB NET` versus `VB.NET`, versioned product names versus base names, and grouped AWS services versus individual services.
4. Some resumes have genuine omissions, especially dense technical resumes where the gold contains dozens of explicitly listed tools.
5. Broad punctuation or fuzzy normalization is unsafe for skills because punctuation distinguishes `C`, `C++`, `C#`, `.NET`, `R` and similar technologies.

The main job-title problems are genuine selection, specificity and OCR errors rather than casing:

- `AVATON BOATSWAIN'S MATE, FUEL'S` versus `Aviation Boatswain's Mate, Fuels` is an OCR error.
- `LIED BUSSER` versus `Lead Busser` is an OCR error.
- `Software Engineer` versus `Data Engineer` or `Python Developer` is a materially different title.
- `Oracle Database Administrator` versus `Oracle Database Administrator Support` is a specificity mismatch.
- `E T L Engineer` versus `ETL Informatica Developer` needs only a controlled acronym/title rule, not unrestricted fuzzy matching.

The next extraction prompt should require skills to be short atomic items explicitly visible in a skills/tools/competencies context and forbid converting responsibility sentences into skills. Production postprocessing can split clearly labelled skill groups into atomic values, while a controlled alias dictionary can handle verified technology spellings. Job-title normalization should be restricted to acronyms, seniority abbreviations and punctuation; semantically different roles must remain errors.

## Normalized comparison v003 plan

Before changing the extraction prompt, normalized v003 tests how much of the skills/job-title gap is caused by safe representation differences. It remains an offline derived experiment with zero LLM calls.

Added comparison rules:

1. Split explicitly labelled groups such as `Programming Languages: Python, Groovy` into atomic skills.
2. Split comma- and semicolon-delimited skill values.
3. Split parenthesized enumerations such as `AWS (EC2, EBS, S3, RDS)` into their atomic technologies.
4. Apply a small controlled alias table: `Cloud Formation -> CloudFormation`, `Amazon Web Services -> AWS`, `Google Cloud Platform -> GCP`, `Apache Kafka -> Kafka`, `Hibernate ORM -> Hibernate`, `Java Script -> JavaScript`, and `VB NET -> VB.NET`.
5. Preserve meaningful technical punctuation; there is no unrestricted punctuation removal or fuzzy matching for skills.
6. Normalize job-title seniority abbreviations `Sr -> Senior` and `Jr -> Junior`.
7. Collapse separated title acronyms such as `E T L -> ETL`, `D B A -> DBA`, and `Q A -> QA`.

These transformations are applied symmetrically to prediction and gold comparison keys. Original stored values remain unchanged. Materially different skills and roles remain FP/FN errors.

### v003 first-run notebook issue

The first attempted v003 analysis run appended no v003 rows. The active Jupyter kernel had cached the previously imported v002 normalization and offline-runner modules, so the restart-safe runner correctly found v002 complete and performed no work. This was not a metric regression or ledger failure. The analysis setup now explicitly reloads `normalization`, `field_scoring`, and `offline_normalized_run` in dependency order before creating a derived experiment. This prevents stale notebook imports from silently executing an older normalization version.

### v003 measured result

The corrected v003 run appended 84 derived rows and made zero LLM calls.

| Metric | v002 | v003 | Change |
|---|---:|---:|---:|
| Overall micro-precision | 0.6127 | 0.6186 | +0.0059 |
| Overall micro-recall | 0.6116 | 0.6249 | +0.0133 |
| Overall micro-F1 | 0.6121 | 0.6217 | +0.0096 |
| Skills precision | 0.4108 | 0.4429 | +0.0321 |
| Skills recall | 0.5005 | 0.5454 | +0.0449 |
| Skills F1 | 0.4512 | 0.4888 | +0.0376 |
| Job titles F1 | 0.7905 | 0.7905 | 0.0000 |

Skills TP increased from 504 to 601. FP also increased from 723 to 756 because atomic splitting exposes additional predicted items, while FN changed only from 503 to 501 because the same atomicization also expands composite gold values. The net F1 gain confirms that inconsistent grouping explained part of the skills gap, but most remaining error is genuine over-extraction, omission or incompatible granularity. Job-title aliases produced no measurable change in this cohort. No unrelated field regressed.

The combined Skills and job titles section improved from approximately `0.5002` to `0.5289` F1, but remains far below the `0.80` threshold. Additional broad aliases are unlikely to close this gap safely. The next meaningful step is to reduce responsibility-sentence over-extraction and improve explicit technical-skill recall, which requires an extraction/prompt or model experiment rather than further unrestricted comparison normalization.

## Normalized comparison v004 plan: date precision

The next offline experiment focuses on date representation and makes zero model calls. Evidence from v003 showed repeated avoidable mismatches such as `2015-05` versus an education gold year of `2015`, `Spring 2018` versus `2018`, `Mar 2020` versus a certification year of `2020`, and `May '16` versus `2016`.

The v004 rules are:

1. Education `start_year`/`end_year` and certification `year` are compared at year precision (`YYYY`), even when either side includes a month or season.
2. Apostrophe years such as `'16` are expanded conservatively to `2016` (00–30) or `19xx` (31–99).
3. Experience dates retain month precision when it exists.
4. When the gold experience date contains only a year, a prediction with the same year plus a month is accepted because the gold annotation does not provide finer precision.
5. Different explicit months remain mismatches; the rule does not hide genuine date errors.
6. Matched prediction/gold date pairs are stored in `matched_value_pairs` for auditable evidence.

This is `field_comparison_v004`, appended to the existing ledger as a new derived experiment. Raw model outputs and previous experiment rows remain unchanged.

### v004 measured result

The v004 derived run completed for all 84 successful baseline resumes and made zero additional model calls.

| Metric | v003 | v004 | Change |
|---|---:|---:|---:|
| Overall micro-precision | 0.6186 | 0.6352 | +0.0166 |
| Overall micro-recall | 0.6249 | 0.6417 | +0.0168 |
| Overall micro-F1 | 0.6217 | 0.6384 | +0.0167 |
| Education start year F1 | 0.3273 | 0.8364 | +0.5091 |
| Education end year F1 | 0.4265 | 0.7941 | +0.3676 |
| Experience start date F1 | 0.7713 | 0.7769 | +0.0055 |
| Experience end date F1 | 0.7586 | 0.7586 | 0.0000 |
| Certification year F1 | 0.1429 | 0.7857 | +0.6429 |

No non-date field changed. The large gains in education and certification confirm that those errors were primarily representation/precision mismatches. Experience dates improved little because most remaining errors are omissions, incorrect dates or different explicit months rather than formatting differences.

## Normalized comparison v005 plan: education institutions

Institution evidence in v004 contained 31 FP/FN pairs where the prediction included the complete gold institution name followed by a city, state or country. Examples included `Colorado State University, Fort Collins, CO`, `University of Chicago - Chicago, IL`, `Nanyang Technological University, Singapore`, and `UCLA, Los Angeles, CA`.

The v005 rules are:

1. Continue applying global Unicode normalization, lowercasing and whitespace collapse.
2. Remove only verified trailing locality suffixes after a comma or spaced dash.
3. Preserve legitimate institutional subunits and campuses, including `Heinz College, Carnegie Mellon University`, `The Ohio State University, Fisher College of Business`, `California State University, Fullerton`, and `University of Michigan - Dearborn`.
4. Normalize the evidence-backed spacing variant `Penn State WorldCampus` to `Penn State World Campus`.
5. Do not fuzzy-match institution names. OCR or extraction errors such as `North Hills` versus `Indian Hills`, `SHENAI` versus `Brenau`, and `Brandeis` versus `Brandman` remain errors.

This is `field_comparison_v005`. It reuses the existing raw inference outputs, appends derived rows to the same ledger, makes zero model calls, and does not alter prior evidence.

## Prompt v003: skill and project boundaries

The five-resume v002 smoke test exposed two source-boundary problems rather than
schema failures. Skill extraction sometimes stopped after a small subset of a
long qualifications list, while another resume produced complete responsibility
sentences as skills. The revised production prompt therefore requires inspection
of every item, preserves a competency phrase when the resume presents it as one
item, splits only explicit enumerations of named skills/tools, and forbids
inventing shortened labels from prose.

Project extraction also treated role labels such as `Exhibitor` and `Member` as
project names and truncated a legitimate colon-bearing title. The revised rule
uses visual title structure, preserves meaningful text after a colon, rejects
participation/authorship labels as names, and prefers a specifically named work
over a nearby generic project-stage label.

No gold annotation is mentioned or encoded in the production prompt. These are
general document-structure rules derived from observed extraction failures.

Comparison normalization `field_comparison_v006` additionally removes explicit
field-of-study labels such as `Major in` when comparing `education.field`. It
does not mutate stored predictions or references and requires no model call.

At the time v003 was prepared, the ledger contained five v002 inference results
and no v003 inference results. The same five development resumes must be used as
the first v003 smoke test before expanding the run.

### Prompt v003 skills result and v004 correction

On the same five-resume smoke set, v003 skills changed from 11 TP, 34 FP and 41
FN (v002 F1 `0.2268`) to 14 TP, 87 FP and 38 FN (v003 F1 `0.1830`). The main
regression was the architect resume, where generic experience duties were mined
as skills and false positives increased from 13 to 61. v003 is therefore
rejected and must not be expanded to the full corpus.

The low exact score also exposes a comparison-target mismatch: several model
values preserve visible source wording, such as `Excellent photography skills`,
while the reference uses a shorter canonical concept such as `Photography`.
The extraction model must not paraphrase source text merely to resemble the
reference. Prompt v004 consequently restores source-faithful extraction, copies
each visibly presented competency item, splits only explicit enumerations, and
forbids mining ordinary experience duties for generic concepts. The project
boundary fixes from v003 remain because they address independent extraction
errors.

Official item-level TP/FP/FN remains strict and auditable. Controlled aliases
and representation normalization remain separate from raw extraction; no broad
semantic or fuzzy matcher is introduced as an official success criterion.

### Review response: operational measurements and atomic skills

The Milestone 5 review requires the complete 86-record resume-parsing
evaluation, field precision/recall/F1, per-field accuracy, confusion examples,
confidence intervals, stronger gold verification, robustness evidence and
computational-cost reporting. The evaluation and analysis notebooks already
retain per-resume field evidence, latency, schema adherence and append-only
experiment identity. Gold verification and the separate 43-category blind set
remain ongoing and must be reported with their verified counts rather than
implied as complete.

Starting with prompt v005, Vertex provider usage metadata is captured per model
attempt: prompt/input tokens, output tokens, total tokens, cached input tokens,
thinking tokens when present, and the raw per-page usage events. Estimated cost
uses the explicitly versioned 2026-08-09 Gemma 4 26B rates of $0.15 per million
input tokens, $0.60 per million output tokens and $0.015 per million cache-hit
tokens. Cloud Billing remains the authoritative cost source. Historical rows
without saved usage metadata remain null and are never backfilled with guessed
token counts.

Prompt v005 changes only the skills target from source sentences to explicit
atomic skill entities. Presentation framing is removed, enumerated skills are
split, and ordinary duties remain excluded. Raw model output is retained for
audit; ESCO concept linking is a separate downstream comparison step and must
not mutate the extracted evidence.

## Job-title extraction diagnosis after v005

The top-level `job_titles` field reached precision `0.7968`, recall `0.7842`, and F1 `0.7905` (TP 149, FP 38, FN 41). `experience.job_title` reached precision `0.8393`, recall `0.7790`, and F1 `0.8080` (TP 141, FP 27, FN 40). Both exceed the documented Milestone 3/5 minimum of 0.75, but job titles are downstream-critical and the remaining errors warrant an extraction experiment.

The main errors are: omitted roles or entire experience sections; employer, education or responsibility text placed in the title field; meaningful modifiers dropped or added; composite titles paraphrased rather than transcribed; and a smaller set of visual transcription errors. Examples include `Mixes Evergarden Landscaping` classified as a title, `Low level development (C/C++)` classified as a title, `Visiting Ph.D. Student` classified as a job, `Falcon Stage Engineer` missing `Vehicle`, and `LIED BUSSER` instead of `Lead Busser`.

The schema originally asked the model to produce the same concept independently in `experience[].job_title` and top-level `job_titles`, while describing the latter as “Normalised.” This conflicted with the production instruction to transcribe visible text. An offline diagnostic that replaced `job_titles` with the baseline experience titles reduced F1 from `0.7905` to `0.7598`, demonstrating that experience omissions must be addressed by the new prompt. The design decision is nevertheless to remove the duplicate model decision: improve experience completeness, derive downstream `job_titles` deterministically, and stop scoring the historical independently curated top-level gold list.

## Prompt v002: boundary accuracy and section completeness

The next inference experiment bundles only changes supported by errors in the 84 successful baseline records. It adds explicit extraction rules for atomic grounded skills; complete and correctly paired experience entries; education field boundaries and date direction; projects including publications, books, exhibitions and presentations; and certifications including licences, training and credentials. Descriptions remain a separate diagnostic and are instructed to preserve visible claims without invention.

Experience and project descriptions are explicitly required word-for-word: no summarising, paraphrasing, rewriting, improving, shortening or adding claims. This makes exact normalized match and token-overlap metrics interpretable while preserving source fidelity.

Top-level `job_titles` is removed from the model-facing schema and from field scoring. The public `CandidateProfile.job_titles` key remains unchanged for downstream compatibility and is derived deterministically from deduplicated non-null `experience[].job_title` values during postprocessing. The historical gold `job_titles` key remains in the source dataset but is ignored by this evaluator.

Two source-image-verified gold corrections are applied through the versioned `education_source_review_v001` correction layer:

1. `automobile__7b9fa0558115d57f`: `degree = Advanced Technical Certificate`, `field = Automotive Technology`. The historical gold duplicated the field inside the degree despite the separate schema fields.
2. `sql_developer__Image_97`: the visible education range is `2007 - Ongoing`, recorded as `start_year = 2007`, `end_year = Ongoing`.

Original annotation files and the gold `job_titles` values are not silently rewritten. The correction version is included in the new experiment identity and ledger metadata.

### Description diagnostic

Description quality is reported in a separate notebook section and is not mixed into field TP/FP/FN. Cosine similarity alone is insufficient because it ignores coverage and can remain high for incomplete text. The diagnostic therefore reports description-count precision/recall/F1, token-overlap F1, cosine similarity, normalized exact-match rate, and a simple combined score of `0.70 × token F1 + 0.30 × count F1`. Because the historical gold descriptions are not guaranteed verbatim source transcriptions, these values are diagnostic rather than acceptance criteria.

### Present/current-status extraction evidence

The baseline contained 57 gold experience `end_date` values representing `Present`, `Current` or `Ongoing`, but only 40 such values were returned. Sixteen resumes had at least one gold current-status value with none returned, including `accountant__44`, `banking__81`, `data_science__33`, `education__135`, `etl_developer__50`, `sql_developer__Image_97`, and `web_designing__Image_19`.

The flattened `experience.current_role` score is optimistic because boolean values are collapsed to a set within each resume; one correctly extracted `false` can hide another entry's missing `true`. Prompt v002 therefore requires every visible current-status word to remain in its corresponding end-date field and sets `current_role = true`. An explicit past end date sets false, while ambiguous status remains null. Education uses the same reading-order rule and permits an ongoing status only in `end_year`.

### Gold-based skills strategy review

Before adding a proposed sentence-length filter, it was simulated against all 1,071 gold skills and the 756 v005 skill false positives. A conservative rule using a 15-word maximum plus action-phrase patterns would reject zero current gold values but remove only 33 false positives (`4.37%`). This is too little benefit for a brittle production rule, especially because future resumes may contain valid longer competencies.

The gold set also deliberately contains phrase-like competencies such as `Working with IT Project managers and development teams`, `Trained in liquor, wine and food service`, `E2E understanding of Liner Operations & Intermodal processes`, and `Hazardous Location Class 1 Div 1 & 2 electrical installations`. Therefore grammar or length alone cannot distinguish skills from responsibilities.

No production sentence filter was added. Prompt v002 instead uses section layout and headings as primary evidence: phrase-like values visibly listed under Skills, Core Competencies or Qualifications are retained, while text outside such sections must be an explicitly named tool, technology, method or competency rather than a complete duty or achievement. Controlled aliasing and safe group splitting remain comparison/postprocessing concerns.

### Atomic gold migration

That earlier source-phrase policy was superseded for the skills field. The
historical 86-resume gold set contained bundled tool lists and proficiency
phrases, so `atomic_skills_v001` now corrects them through the versioned gold
correction layer. The original JSONL remains unchanged as audit evidence.
Corrections split explicitly named tools, remove proficiency framing, exclude
one duty-only annotation, and deduplicate overlaps introduced by expansion.
After corrections, the loader rejects obvious comma/semicolon bundles and
leading proficiency phrases. The blind 43 annotation instructions use the
same contract and will be checked by the same loader once records are marked
annotated.

Vendor-product expansion is a deterministic comparison rule rather than a
model rewriting instruction. A controlled alias table covers unambiguous
Microsoft, Adobe, Google and cloud-product names—for example `MS Excel` versus
`Microsoft Excel`, `Photoshop` versus `Adobe Photoshop`, and `G Suite` versus
`Google Workspace`. Generic or uncertain tokens such as bare `Access`, `Docs`
or `Sheets` remain unchanged unless the vendor is explicitly present.

### Project and certification source review before the full run

The 84-resume v004 evidence showed project F1 `0.5306` and certification F1
`0.5596`. Source-image review separated extraction errors from annotation
errors before spending on another full inference run.

Project extraction errors included appending an explanatory sentence to names
such as `Documentation AID`, using `Becoming an Author` instead of the printed
book title, treating an event as a project, and inventing projects from ordinary
experience. The prompt now uses visual structure plus grammatical boundaries:
an explanatory clause after a colon belongs to description, while a colon that
is genuinely part of a styled title remains. Books use their printed titles,
and projects cannot be inferred from duties, awards, events or technologies.
The gold project `Feather` incorrectly treated the phrase `CSS grid systems` in
its description as an explicitly used technology; that inferred `CSS` value was
removed through the versioned correction layer.

Certification review found omitted completed training, bundled certificates,
credential IDs included inside names, and a qualification/issuer boundary
error. Verified corrections cover the affected Automobile, Civil Engineer,
Designer, Education, Mechanical Engineer and Operations Manager records. The
Education record now includes all visibly listed Professional Development /
Training entries rather than four selected examples. Original annotation JSONL
is retained unchanged.

The certification prompt now scans the complete resume because credentials were
visibly present under Summary, Skills, Education and experience bullets as well
as dedicated headings. It creates one entry per credential, separates IDs,
issuer and year, and explicitly excludes awards, honours, memberships, ordinary
skills, duties and training delivered by the candidate. The resulting full-run
configuration is prompt `v006_atomic_skills_project_certification` with
evaluation mode `production_output_atomic_skills_project_certification_usage_v010`.

### Description evaluation simplification

Description evaluation now covers experience entries only. Each gold experience
is paired with the same predicted experience using company, job title and dates;
description text is never used to select its own match. A deterministic
`TfidfVectorizer` cosine compares the paired descriptions, requiring no language
or embedding model. Missing experiences or descriptions score zero and gold
entries without descriptions are not applicable. On the saved 84-resume v004
predictions, 199 gold descriptions were applicable, matched-description coverage
was `0.7387`, overall TF-IDF cosine including missing entries was `0.4402`, and
matched-only TF-IDF cosine was `0.5960`. These remain diagnostic because the
historical gold descriptions are not guaranteed verbatim source transcriptions.

A manual failure audit clarified that `0.7387` is a same-experience identity
match rate, not description-field presence. All 147 identity-matched experiences
had a predicted description; the 52 zero rows failed title/company/date matching.
Of those 52, 51 belonged to resumes that still contained at least one predicted
description and 30 had a description at the same list index. This points to
experience extraction/alignment errors and incorrect historical identity fields,
not systematic omission of the description key.

For the 147 matched entries, the prediction retained on average `87.51%` of gold
description tokens, but only `43.91%` of prediction tokens appeared in gold. The
median prediction was `2.16x` the gold description length. Source review confirms
that many gold descriptions are short summaries while predictions retain longer
visible bullet lists; this valid additional text lowers TF-IDF cosine. Existing
TF-IDF processing already ignores case, punctuation and bullet formatting, so
more aggressive normalization would conceal content differences rather than fix
the benchmark. The analysis chart therefore labels coverage as same-job matching
and reports matched-only similarity separately.

### Prompt v002 five-resume development smoke test

The first prompt-v002 smoke test completed all five selected development resumes with zero failures and 100% raw extraction-schema validity. Raw model responses correctly omitted the derived `job_titles` field, while every production output contained the list derived from `experience[].job_title`. Mean resume latency was `15.680 s`, effectively unchanged from the same five baseline resumes (`15.637 s`).

On this small paired sample, experience titles, companies, locations, dates and current-role values remained perfect after normalized scoring. Projects name F1 improved from `0.000` to `0.600`, and the description diagnostic improved from `0.608` to `0.674`; description-count F1 rose from `0.900` to `0.971` and token F1 from `0.483` to `0.547`.

The run is not yet suitable for expansion because skills F1 decreased from `0.305` to `0.227`, contact name F1 from `0.800` to `0.600`, contact location from `1.000` to `0.857`, and education field from `0.667` to `0.400`. The skills prompt reduced gross over-extraction for `agricultural__dceaa326c82da46e`, but also omitted valid tools such as computers, electronic equipment, MS Office and yield monitor systems. For `architect__38d167423f55cd85`, it copied qualification bullets too literally, returning phrases such as `ability to act on own initiative...` instead of the competency core. Project recovery also produced three spurious names and missed the legitimate colon-containing title `Best Before: Archivised`, showing that a rule treating colon text as a subtitle is unsafe.

The next prompt revision should add explicit contact transcription/completeness, extract the competency core while removing framing such as `ability to`, `knowledge of` and `proficient with`, preserve all explicitly listed tools, and identify project titles by visual structure rather than truncating at punctuation. Do not run the remaining development set until that revision passes another smoke test.

### Positional experience-description alignment

This issue was in our evaluation scorer, not necessarily in the model output.
The original description diagnostic required title, company or date agreement
before comparing two descriptions. This incorrectly turned errors in those
identity fields into apparent missing-description errors. The scorer now pairs
`reference.experience[i]` with `prediction.experience[i]`, matching the ordered
list contract of the extraction schema. Identity agreement remains visible as a
diagnostic only and cannot suppress description scoring. Missing positional
entries or descriptions still score zero, and gold entries without a description
remain not applicable. A skipped or invented experience can shift later entries,
so low identity scores should be inspected when interpreting positional results.

### Versioned experience-description gold correction

All 86 source PDFs were processed with local OCR. Saved v004 descriptions were
used only as transcription candidates: a candidate was accepted when ordered
token sequences were grounded in the source OCR at `>= 0.75`, it expanded the
existing annotation by at least `1.20x` (or filled an empty description), and
the experience identity was reliable. Ten low-identity candidates were
inspected separately: six represented the same experience with malformed or
missing identity metadata and were retained, while four genuine positional
shifts were rejected. This produced 116 auditable corrections in the versioned
description-correction JSONL; the original Milestone-2 gold JSONL remains
unchanged. Each correction records the previous description, corrected text,
grounding score, identity score and verification method.

This is an OCR-assisted benchmark repair, not independent human annotation, and
must be disclosed as such. The offline normalized rescorer now loads the current
versioned gold rather than copying the stale reference embedded in an earlier
inference row. Therefore existing model predictions can be rescored without any
additional Vertex AI call.

A read-only preliminary rescore of the 84 saved v004 predictions against this
corrected layer found 201 applicable gold descriptions, 179 same-index predicted
descriptions (`0.8905` coverage), `0.8353` mean TF-IDF cosine where present, and
`0.7439` overall cosine with missing descriptions scored zero. The corresponding
pre-correction values were `0.8894`, `0.5446` and `0.4844`. The large similarity
change confirms that abbreviated historical annotations were depressing the
diagnostic, but the corrected result must not be presented as a blind or wholly
human-verified benchmark because saved v004 text supplied the candidates that
were accepted only after source-OCR grounding.

### Evidence-backed skill comparison v009

During the in-progress v006 run, the first 46 resumes produced skill F1 `0.4829`
under v008 comparison, versus `0.4882` for v004 on the same resume IDs. Error
inspection showed unambiguous representation mismatches including `JS/jQuery`
versus separate `JavaScript` and `jQuery`, `MS SQL 2005/2008` versus `SQL Server`,
and phrase-boundary variants for electrical construction, construction codes,
scheduling and enterprise information architecture. These exact observed cases
were added to deterministic comparison normalization; no fuzzy or general
semantic matching was introduced. Under version
`field_comparison_v009_evidence_backed_skill_aliases`, the same partial v006
sample improves to precision `0.4645`, recall `0.5377` and F1 `0.4984`. The
remaining gap therefore cannot be explained by these aliases alone and should
be separated into genuine omissions and further source-verified canonical
equivalences after the full run completes.

### Dedicated-section certification policy v001

The certification gold was audited against all source-PDF OCR using an explicit
production policy: retain credentials only under clearly labelled credential
sections such as Certifications, Certificates, Licences, Registrations,
Professional Development / Training, Additional Training, or a combined
Education / Certifications section. Entries found only in Summary, Skills,
Highlights, ordinary Education, Experience, or unlabeled text are excluded.
This versioned policy retains 46 of the previous 78 certification records and
records the accepted source heading per resume; the original gold remains
unchanged.

Changing gold alone did not improve the saved model score. The complete v004
certification F1 becomes `0.5062`, while the first 46 v006 resumes score `0.4909`
under this policy (down from `0.5693` under the broader gold). This is expected:
v006 was explicitly instructed to scan the entire resume, so credentials it
extracts from out-of-policy sections now count as false positives. The result is
evidence of a production-policy mismatch, not a normalization problem. A future
prompt must restrict certification extraction to dedicated sections before this
gold policy can be evaluated fairly; prediction values must not be silently
discarded during scoring merely to improve F1.

Against the current dedicated-section gold, the original v001 full run scores
project-name F1 `0.1905` and certification-name F1 `0.4096`. The immediately
preceding full v004 prompt scores project-name F1 `0.5882` and
certification-name F1 `0.3918`; its aggregate Projects and Certifications F1
scores are `0.5417` and `0.5062`, respectively. Thus the prior prompt had already
improved project identification substantially, but had not solved certification
names under the clarified policy.

Project-name failures in v004 are predominantly instruction and boundary errors:
descriptions were appended to four valid Business Analyst project titles,
ordinary work such as a festival, change-management strategy, crawler and
recommendation engine was promoted to projects, and `Becoming an Author` was
used instead of the printed book title. These are not primarily OCR failures.

Certification-name failures have three causes. First, many false positives are
now correctly out of scope because they came from Summary, Skills, Highlights or
unlabelled text. Second, dedicated sections were missed, including two Designer
licences, the ETL certifications and Professional Development / Training items.
Third, genuine vision/transcription errors corrupted names such as `Data to
Insights Prof. Certificate`, `HIPPA & General Clinical Practices`, `ITIL`,
`PRINCE2`, and complete Oracle certification names. The next certification
prompt should therefore enforce the dedicated-section boundary and completeness,
but prompt wording alone cannot guarantee correction of the remaining OCR-like
name corruption.

### Gemini atomic-skill boundary prompt v007

The five-resume Gemini v006 smoke test improved normalized skill F1 from Gemma's
`0.5197` to `0.6099`, but two resumes dominated the remaining errors. Gemini
visually transcribed their skill phrases accurately yet retained proficiency
framing and coordinated concepts instead of returning the atomic representation
required downstream. The Skills prompt was therefore shortened and made
operational with exact boundary examples for plant anatomy/transplant methods,
budgeting/negotiating, chemical application, mower operation, leadership,
Federal/State Law, and bookkeeping/Tally. This is prompt v007 and must be tested
as a new five-resume experiment before expansion; prior v006 evidence remains
unchanged in the append-only ledger.

The v007 rerun completed all five resumes successfully. Skill recall improved
from `0.6418` to `0.7164`, but precision fell from `0.5811` to `0.5333`; F1 moved
only from `0.6099` to `0.6115`. The Agricultural example recovered three atomic
matches but over-split chemical application and mower-operation phrases and
still retained framing such as `leadership skills`. It also introduced unrelated
items including logistics, product placement and rural-work ability. Other
resumes added summary-derived concepts absent from gold. Average latency improved
from `19.147 s` to `18.033 s` but remained above Gemma's `16.202 s` on the same
five resumes. This demonstrates that additional prompt examples trade precision
for recall without solving canonical skill construction; further prompt-only
iteration is not justified before a deterministic/ESCO-backed post-extraction
skill-resolution stage is evaluated.

### Five-resume manual skill-gold review pack

A source-first manual review pack was prepared for `accountant__44`,
`accountant__fac6c23d5aafc14e`, `advocate__3bbf2f150c0573b5`,
`advocate__ba77440de8f99831`, and `agricultural__Image_70`. Each case preserves
the source PDF, current gold skills, Gemini v006 prediction, and Gemini v007
prediction. The sample covers incomplete or curated gold, summary-scope
ambiguity, languages represented outside the skills section, coordinated legal
skills, and prose-to-atomic skill boundary failures.

No gold was changed while assembling the evidence. The accompanying manual
review document records preliminary source evidence and explicit reviewer
decisions. Any accepted correction must be applied as a new versioned gold set
and justified by the PDF rather than by agreement with model output.

The first manual check, `accountant__44`, confirmed a gold-policy inconsistency.
Governmental accounting and accounts payable/receivable are visibly supported
by the professional summary, while bookkeeping is explicitly printed several
times in the skills areas but is absent from the current gold. Thus these
particular gold values are not hallucinated, but their selective inclusion makes
the record unsuitable for fair exact-match evaluation until a single annotation
scope is applied consistently.

Following visual confirmation, `accountant__44` received the first complete
`skill_sections_v001` replacement. Summary- and work-history-derived values were
removed, and the gold now represents competencies and products visibly printed
inside the resume's skill areas, including bookkeeping. The historical source
JSONL remains unchanged and the correction is applied by the versioned gold
loader. Controlled scoring aliases already mapped Word, Excel, PowerPoint and
Outlook to their unambiguous Microsoft product names; the equivalent bare
`Access` to `Microsoft Access` mapping was added. These mappings affect only
comparison keys and never mutate the model's stored output.

### Dataset-wide explicit skill-section gold v001

The strict section-only policy was applied to all 86 gold records without using
any model predictions. Historical skills were retained only when grounded in a
detected Skills, Technical Skills, Key Skills, Core Competencies, Qualifications,
Tools, Technologies, Environment, Expertise, or Professional Forte section in
source-PDF OCR. The original Milestone-2 JSONL remains unchanged. The versioned
gold contains 441 atomic skills after existing source-reviewed atomic corrections,
compared with 1,071 before the section restriction; 43 resumes contain no scored
skills under this strict policy. An audit JSONL records the old/new counts,
removed values, detected headings, derivation method, and OCR-heading review flag
for every resume.

A no-cost rescore of the latest 83 saved Gemma v006 predictions produced 198 TP,
1,143 FP and 150 FN: precision 0.1477, gold coverage/recall 0.5690, F1 0.2345 and
Jaccard overlap 0.1328. The decrease is important evidence: the saved extraction
outputs contain many skills outside the newly restricted gold scope. Therefore,
changing gold alone does not raise the score; extraction and annotation must use
the same section contract. Gold coverage is reported explicitly but does not
replace precision or F1, because predicting many extra values can achieve high
coverage while remaining inaccurate.

Two source-observed grammatical skill variants were added to normalized scoring:
singular/plural `Bank reconciliation(s)` now shares one comparison key, and
`Preparing financial statements` shares a key with `Financial statement
preparation`. These are controlled aliases rather than unrestricted stemming or
semantic similarity. They affect only comparison keys and cannot make broader
skills such as `Accounting` match a specialised accounting competency.

### Whole-section skills text diagnostic

A practical secondary skills metric now joins each predicted and gold Skills
list into one text block and computes pair-local TF-IDF cosine similarity using
word unigrams and bigrams. This tolerates differences in list boundaries and
allows combined phrases to receive partial credit without silently converting
them into exact entity matches. It is reported beside strict entity F1, not as a
replacement for the reviewer's requested TP/FP/FN evidence.

On the saved section-only gold, Gemma v004 has skills-section presence coverage
1.0000, mean cosine 0.4700 and median cosine 0.4209 across 41 applicable resumes.
Gemma v006 has presence coverage 1.0000, mean cosine 0.4735 and median cosine
0.4293 across 40 applicable resumes. Thus v006 is marginally better on whole-text
similarity even though v004 remains slightly better under strict entity F1.

### Original-gold hybrid skills evaluation

A separate skills-only overlay restores all 1,071 untouched Milestone-2 skill
values across 86 resumes while retaining the current corrected gold for every
other field. This avoids rewriting either the original annotations or the
section-restricted experiment. Skills containing at most three words use
controlled normalized entity matching. Values longer than three words, or
containing composite punctuation, use pair-local unigram/bigram TF-IDF cosine
with a 0.50 acceptance floor. Best-match scores are calculated symmetrically to
produce soft precision, gold coverage and F1.

Against this original-skills overlay, saved Gemma v004 scores mean hybrid
precision 0.5897, coverage 0.5981 and F1 0.5727 across 84 resumes. Saved Gemma
v006 scores precision 0.5886, coverage 0.5916 and F1 0.5699 across 83 resumes.
The similar results indicate that atomic prompt v006 did not materially improve
skills over source-faithful v004 under a metric designed for the original mixed
annotation granularity.

### Gemini full source-faithful Skills run v008

The next Gemini 3.5 Flash experiment is configured for all 86 resumes with
medium thinking and no atomic Skills transformation. The Skills contract now
reads explicit skill-style sections completely and preserves each visible line,
bullet or grouped entry as one value with its wording, grouping, product spelling
and technical punctuation intact. It forbids splitting, expansion,
canonicalization, summarization, paraphrasing and mining skills from summaries,
education, projects, certifications or work-history prose. General grounding,
schema completeness, privacy-safe locations and case-insensitive deduplication
remain active.

The experiment is versioned as `v008_source_faithful_skill_lines` with evaluation
mode `production_output_gemini35_flash_source_skill_lines_full_v013`. The earlier
five-resume Gemini smoke records remain preserved in the append-only ledger but
have a different experiment key and cannot be mistaken for completed rows in
this run. Per-attempt and per-resume latency, prompt/output/thinking/total tokens,
cache tokens and estimated USD cost remain recorded. The notebook starts with
`LIMIT=5`; the limit can be increased cumulatively after each manual review.

Prompt v009 tested a stronger visual section-boundary instruction on the same
five resumes. It failed: summary-derived skills persisted and increased for one
accountant, while grouped source lines such as the Microsoft Office and reporting
tool groups were split into atomic values. The experiment was therefore rejected
and the active evaluation, analysis selection and manual-review exports were
restored to accepted prompt v008. The v009 rows remain only in the append-only
ledger as negative experimental evidence.
