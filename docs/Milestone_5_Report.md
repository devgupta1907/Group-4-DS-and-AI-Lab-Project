# Milestone 5 Report: Model Evaluation and Experimental Analysis

## Executive Summary

Milestone 5 evaluates the resume-parsing component of the AI Career
Recommendation System. The evaluated system converts a resume into a validated,
PII-minimised candidate profile. It uses a multimodal large language model (LLM)
with deterministic post-processing and schema validation; no model weights are
trained locally.

Three controlled experiments were completed on five pinned, human-annotated
development resumes:

1. Gemma 4 31B prompt ablation: baseline prompt (`v001`) versus a prompt requiring
   verbatim description copying (`v002`).
2. Model baseline comparison: Gemma 4 31B versus Gemini 3.5 Flash using `v002`.
3. Input-pipeline ablation: direct page vision versus local Docling OCR/layout
   extraction followed by text input to both Gemma 4 31B and Gemini 3.5 Flash.

The strongest prompt result was `v002`, which increased the description score
from 0.442 to 0.545 (+23.4% relative), although average latency increased from
76.0 s to 96.0 s. Gemini 3.5 Flash was substantially faster than Gemma 4 31B
(14.3 s versus 96.0 s average) and achieved a higher exact-copy rate on returned
descriptions (0.917 versus 0.333). The full-profile result is model-dependent:
Docling improved Gemma's strict paired macro F1 from 0.846 to 0.891, but reduced
Gemini 3.5 Flash from 0.887 to 0.800. A scoring audit found that exact
combined-field matching substantially exaggerates the largest difference, so
these results are treated as strict fidelity scores rather than final semantic
accuracy rankings.

The system is suitable for continued integration and expanded evaluation, but
not yet ready for an unconditional production claim. The held-out 52-resume
test split has deliberately not been used for prompt tuning and should be
evaluated once after the configuration is frozen.

## 1. Experimental Setup

### 1.1 Frameworks and libraries

The backend uses FastAPI, Pydantic, Google Gen AI, LangSmith, PyMuPDF,
python-docx, Pillow, Docling, pandas, and psutil. Deterministic Python evaluators
calculate all reported field metrics; no LLM judge is used.

### 1.2 Dataset

The versioned gold dataset contains 87 annotated resumes:

| Split | Resumes | Intended use |
|---|---:|---|
| Development | 35 | prompt/pipeline selection |
| Held-out test | 52 | one-time final evaluation |
| Total | 87 | |

The reported experiments use five pinned development resumes spanning SAP
Developer, Network Security Engineer, SQL Developer, Python Developer, and Data
Science categories. The test split was not used for tuning.

### 1.3 Evaluation workflow

```text
Pinned resume + human gold profile
              |
      route by file type
              |
   +----------+-----------+
   |                      |
direct page images   Docling Markdown
   |                      |
   +------ same prompt, model, temperature ------+
                             |
                     structured extraction
                             |
                   merge and normalisation
                             |
                 schema and PII validation
                             |
              deterministic comparison to gold
```

## 2. Evaluation Methodology

### 2.1 Protocol and ground truth

Each prediction is compared with a human-reviewed gold profile transformed into
the production schema. Matching is case- and whitespace-insensitive. List
sections are treated as sets because ordering is not meaningful. Education and
experience entities are matched by identifying field pairs; date accuracy is
then computed separately after normalising equivalent date formats.

Empty prediction and empty gold sections score 1.0 because absence is a valid
state. This avoids penalising freshers or resumes without projects.

### 2.2 Baselines

- prompt baseline: `v001`, with no explicit verbatim-copy rule;
- model baseline: Gemini 3.5 Flash compared with Gemma 4 31B;
- preprocessing baseline: direct page vision;
- preprocessing alternative: Docling OCR/layout extraction followed by text.

### 2.3 Validation approach

Cross-validation is not applicable to this API/prompt experiment. The
development/test separation is used instead. Prompt and pipeline decisions are
made on development data, followed by one frozen evaluation on the held-out test
set.

### 2.4 Success criteria

The implemented prompt acceptance criteria require exact-source rate at least
0.80, description-count recall at least 0.80, schema success of 1.00, and no more
than 25% latency regression. At system level, schema-valid and PII-clean rates
should remain 1.00. A final deployment threshold for macro profile F1 should be
declared before the 52-resume test run.

## 3. Performance Metrics

### 3.1 Extraction metrics

For each set-valued field:

- **Precision** = correct extracted items / all extracted items.
- **Recall** = correct extracted items / all gold items.
- **F1** = harmonic mean of precision and recall.
- **Macro profile F1** = unweighted mean of F1 values for nine profile sections
  plus exact name match. It gives small sections equal importance.
- **Date accuracy** = correctly normalised dates / supported dates for matched
  entities.

### 3.2 Safety and completeness metrics

- **Schema-valid rate**: fraction passing the production schema gate.
- **Coverage**: fraction of expected profile sections populated.
- **PII-clean rate**: fraction without detected email or phone leakage.

### 3.3 Description-grounding metrics

- **Exact-source rate**: returned descriptions found word-for-word in extracted
  source text.
- **Source-window cosine** and **word F1**: near-verbatim similarity to the best
  similarly sized source passage.
- **Source fidelity** = 0.50 × exact-source rate + 0.25 × source cosine +
  0.25 × source-window word F1.
- **Description-count recall**: returned count / annotated count, capped at 1.
- **Description score** = 0.70 × source fidelity + 0.30 × count recall.

Gold-description similarity is diagnostic only because the older annotations
are incomplete and inconsistent.

### 3.4 Computational metrics

End-to-end latency is separated into local preprocessing time and provider model
time. Process resident-set size (RSS) is sampled before and after each run.
Provider retry count and failure type are also recorded.

## 4. Experimental Results

### 4.1 Prompt ablation: Gemma 4 31B

| Metric | `v001` baseline | `v002` verbatim | Change |
|---|---:|---:|---:|
| Description score | 0.442 | **0.545** | +0.103 |
| Source fidelity | 0.374 | **0.521** | +0.148 |
| Exact-source rate | 0.200 | **0.450** | +0.250 |
| Description-count recall | 0.600 | 0.600 | 0.000 |
| Mean latency | **76.0 s** | 96.0 s | +26.3% |

The explicit copy rule improved fidelity but did not recover omitted
descriptions. It narrowly exceeded the allowed 25% latency regression and did
not meet the 0.80 exact-source or count-recall targets. Therefore, `v002` is the
better prompt of the two, but the prompt experiment does not by itself satisfy
all acceptance criteria.

### 4.2 Earlier description-only model comparison with prompt `v002`

| Model | Successful runs | Mean latency | Exact-copy rate* |
|---|---:|---:|---:|
| Gemma 4 31B | 5/5 | 96.0 s | 0.333 |
| Gemini 3.5 Flash | 5/5 | **14.3 s** | **0.917** |

\*Exact-copy rate is calculated over returned descriptions. Only three of five
resumes produced descriptions for each model, so omission must be considered
alongside this rate.

Gemini was 6.7× faster on average and copied returned descriptions more
faithfully. This comparison evaluates description behaviour, not the complete
profile F1. The full-profile comparison below supplies the stronger evidence.

### 4.3 Full-profile 2×2 accuracy comparison

| Model and input | Runs | Macro F1 | Skills F1 | Job titles F1 | Education F1 | Experience F1 | Coverage |
|---|---:|---:|---:|---:|---:|---:|---:|
| Gemma 4 + direct vision | 5/5 | 0.816 | **0.690** | 0.650 | 0.400 | 0.650 | **0.880** |
| Gemma 4 + Docling | 4/5 | **0.891** | 0.663 | **1.000** | **0.750** | **0.750** | 0.825 |
| Flash 3.5 + direct vision | 5/5 | **0.887** | 0.763 | **1.000** | **0.533** | **0.800** | 0.860 |
| Flash 3.5 + Docling | 5/5 | 0.800 | **0.817** | 0.650 | 0.400 | 0.600 | **0.880** |

#### Scoring audit

These are strict normalized exact-match scores, not semantic-accuracy scores.
An audit of the largest difference found that both Flash pipelines returned the
same number of core entities for the Python resume:

| Section | Gold | Direct vision returned | Docling returned |
|---|---:|---:|---:|
| Job titles | 4 | 4 | 4 |
| Education | 3 | 3 | 3 |
| Experience | 4 | 4 | 4 |
| Projects | 0 | 0 | 0 |

Nevertheless, Docling received job-title F1 0.25 and education/experience F1
0.00. The evaluator matches the combined strings `degree|institution` and
`job_title|company` exactly after only case and whitespace normalization. This
can over-penalise harmless punctuation and abbreviations.

An offline similarity diagnostic supports this explanation. For Docling's three
education entries, two best-match string similarities were 0.903 and 0.977; for
experience, three of four were 0.818–0.865. They are scored as zero by the
current exact matcher. However, inspection of the actual Docling Markdown also
found genuine OCR corruption such as `Python Developer` becoming `P EM` and
`09/2012` becoming `4100201`. The difference is therefore a mixture of strict
scoring effects and real information loss; it is not merely punctuation.

Accordingly, the table is retained as **strict extraction fidelity**, while
model selection is deferred until a tolerant field-aware metric and a small
manual review are added. Appropriate matching should normalize punctuation and
common abbreviations, compare entity fields separately, and use a declared
fuzzy threshold or human adjudication for borderline pairs.

Schema-valid rate, PII-clean rate, certifications F1, technologies F1, and name
match were 1.000 for every configuration. Projects F1 was 0.800 except for
Gemma + Docling, which scored 0.750 over four successful cases.

The main result is an interaction between preprocessing and model. Docling
improves Gemma, particularly job-title, education, and experience extraction.
For Flash, Docling improves skills and coverage but worsens job titles,
education, experience, and overall macro F1. It should therefore not be enabled
as a model-independent default.

Flash per-resume macro F1 makes the regression clear:

| Resume | Direct vision | Docling | Difference |
|---|---:|---:|---:|
| SAP Developer | 0.855 | 0.872 | +0.017 |
| Network Security | 0.888 | 0.900 | +0.013 |
| SQL Developer | 0.995 | 0.995 | 0.000 |
| Python Developer | **0.935** | 0.543 | **-0.392** |
| Data Science | **0.762** | 0.692 | -0.069 |

Flash + direct vision has the highest complete strict-score result and avoids
the demonstrated OCR information-loss failure. A tolerant score should still be
reported alongside the strict score before making a broader claim. Gemma +
Docling has a slightly higher conditional mean but failed on one case.

### 4.4 Gemma direct vision versus Docling

| Metric | Direct vision | Docling text |
|---|---:|---:|
| Successful runs | 5/5 | 4/5 |
| Macro profile F1 | 0.816 | **0.891** |
| Schema-valid rate | 1.000 | 1.000 |
| PII-clean rate | 1.000 | 1.000 |
| Coverage | **0.880** | 0.825 |
| Skills F1 | **0.690** | 0.663 |
| Job-title F1 | 0.650 | **1.000** |
| Education F1 | 0.400 | **0.750** |
| Experience F1 | 0.650 | **0.750** |
| Mean preprocessing time | **1.11 s** | 10.05 s |
| Mean model time | 244.08 s | **68.87 s** |
| Mean total time | 245.22 s | **78.94 s** |

These aggregate means have unequal sample sizes because the Python Developer
Docling call failed after provider retries. Across the four complete pairs,
Docling changed macro F1 as follows:

| Resume category | Direct vision | Docling text | Difference |
|---|---:|---:|---:|
| SAP Developer | 0.842 | 0.847 | +0.005 |
| Network Security | 0.900 | 0.978 | +0.078 |
| SQL Developer | 0.991 | 0.991 | 0.000 |
| Data Science | 0.650 | 0.750 | +0.100 |
| **Paired mean** | **0.846** | **0.891** | **+0.046** |

Docling adds approximately 9 s of local preprocessing but substantially reduces
the size of the provider input (mean 2,367 text characters versus approximately
2.71 MB of rendered image bytes). This likely contributes to lower successful
call latency; it is an inference, not a directly measured causal result.

### 4.5 Latency after the accuracy comparison

| Flash metric | Direct vision | Docling |
|---|---:|---:|
| Mean preprocessing | **1.03 s** | 9.66 s |
| Mean model time | 68.63 s | **32.24 s** |
| Mean total time | 69.67 s | **41.90 s** |
| Mean provider retries | 0.60 | 0.60 |

The means include retry and backoff time. Flash/direct vision's Python case took
approximately 280 seconds after three retries. Docling is faster on average,
but that advantage is secondary to its lower Flash extraction accuracy.

### 4.6 Overall system performance

All 19 successful full-profile runs were schema valid and PII clean. The Gemma
+ Docling Python case was retried again but repeatedly timed out, so its missing
score remains a reliability failure. Final model selection is pending corrected
semantic/tolerant scoring.

## 5. Baseline Comparison

Docling improved Gemma's paired macro F1 by 0.046 absolute (5.4% relative), but
reduced Flash macro F1 by 0.086 absolute (9.7% relative). All configurations
maintained schema and PII performance. Docling should not be enabled globally
without a quality-aware routing or fallback policy.

The strict full-profile comparison places Flash + direct vision first among
complete runs, but the scoring audit prevents treating that ranking as final.

## 6. Parameter Analysis

The project does not train weights, so the explored settings are inference and
pipeline parameters:

| Parameter | Values explored | Selection/evidence |
|---|---|---|
| Prompt | `v001`, `v002` | `v002` has higher description fidelity |
| Model | Gemma 4 31B, Gemini 3.5 Flash | Gemini leads speed/copy fidelity; full-profile comparison pending |
| Input strategy | direct vision, Docling text | Docling leads paired macro F1; reliability confirmation pending |
| Temperature | 0 | retained for repeatability |
| Retry schedule | bounded backoff | prevents unlimited API calls |

Learning rate, batch size, optimizer, and epochs are not applicable. Final
selection should use the frozen configuration on all 52 held-out resumes.

## 7. Ablation Study

Three ablation results quantify component contribution:

1. **Without the verbatim-copy instruction (`v001`)**: description score falls
   from 0.545 to 0.442 and source fidelity falls from 0.521 to 0.374.
2. **Without Docling under Gemma**: paired macro profile F1 falls from 0.891 to
   0.846 on the four successful pairs.
3. **Without Docling under Flash**: macro profile F1 improves from 0.800 to
   0.887 across five pairs, demonstrating that preprocessing cannot be assessed
   independently of the model.

The second comparison is specifically an input-representation ablation, not a
model ablation: prompt, model, temperature, gold records, and scoring remain
fixed.

## 8. Error and Scoring Analysis

### 8.1 Observed failure

The Gemma + Docling Python Developer run ended in `ProviderError` after bounded
retries and again timed out when retried. It produced no Gemma profile metrics
and remains an operational failure. Flash + Docling completed on the same
resume, enabling the separate OCR-quality analysis below.

### 8.2 Extraction weaknesses

- Two of five resumes produced no descriptions in both model-comparison groups.
  Exact-copy rate alone therefore overstates performance unless omission is
  reported.
- Direct vision had lower job-title, education, and experience F1 than Docling
  on the successful aggregate.
- Docling had slightly lower skills F1 and coverage, suggesting that OCR/text
  conversion can omit or fragment visually presented skill content.
- Education date accuracy for Docling was 0.5 on four supported dates, compared
  with 1.0 on two supported direct-vision dates. Support is small and unequal.
- An unusually slow direct-vision Python Developer call (872.3 s total) strongly
  affects the direct-vision mean.

#### Representative failure: Docling OCR corrupts Python-resume fields

The Python Developer resume demonstrates genuine OCR information loss, rather
than only an overly strict evaluator. The parser was attempting to identify four
experience/job-title records and their dates:

| Intended value in the gold profile | Docling Markdown | Flash structured output |
|---|---|---|
| `AWS Data Engineer` | `AWS DATA ENGINEER` | `AWS DATA ENGINEER` |
| `Data Engineer` | `DE X ENGINEER` | `DE X ENGINEER` |
| `Big Data Engineer / Hadoop Developer` | `BIODATA ENGINEER HADDOP DEVELOPER` | `BIODATA ENGINEER HADDOP DEVELOPER` |
| `Python Developer` | `P EM` | `P EM` |
| `01/2022` | `01/0029m` | `01/0029m` |
| `09/2012` | `4100201` | `4100201` |

The clean forms `Big Data Engineer`, `Hadoop Developer`, `Python Developer`,
`01/2022`, and `09/2012` were absent from the Docling Markdown. Flash therefore
structured corrupted source text rather than independently introducing these
errors. Recovering the intended values would have required unsupported guessing.

This explains why the Docling pipeline preserved the expected counts—four job
titles, three education entries, and four experience entries—while receiving
low value-level F1. Boundary-punctuation normalization cannot repair `P EM` into
`Python Developer` or `4100201` into `09/2012`. This case should therefore be
classified as a true OCR failure. Direct vision avoids this lossy intermediate
representation by reading the resume page itself.

The example motivates a conditional input policy: use Docling only when OCR
quality checks pass, and fall back to direct vision when headings, dates, or
tokens show corruption. Useful checks include malformed-date rate, unusual
single-letter fragments, OCR confidence, dictionary/role-title coverage, and
agreement between native PDF text and OCR where both are available.

### 8.3 False positives and false negatives

The saved de-identified results contain aggregate field precision and recall but
not item text. False positives correspond to predicted entities absent from the
gold set; false negatives correspond to gold entities omitted by the model.
Representative text examples must be reviewed only from the local protected run
artifacts and redacted before inclusion in a public appendix.


## 9. Model Robustness

The five cases cover multiple professional categories and varied scanned-resume
layouts, but are not sufficient to establish robustness. Evidence currently
supports:

- schema and PII-gate consistency across all successful runs;
- benefit from Docling on several scanned layouts;
- sensitivity to provider throttling and long-tail latency;
- risk of description omission under both tested models.

Required robustness tests include multi-page resumes, low-resolution scans,
rotated pages, tables, multi-column layouts, uncommon date formats, non-English
content, empty sections, malformed uploads, and prompt-injection text embedded
inside a resume. Adversarial security testing should remain defensive and must
verify that document content cannot override the system instruction.


## 11. Limitations

- only five of 35 development resumes were used in the reported experiments;
- only four complete direct-vision/Docling pairs succeeded;
- held-out test performance is not yet available;
- provider-side nondeterminism and throttling remain;
- cost and token usage were not recorded;
- gold descriptions are incomplete/inconsistent;
- empty-vs-empty sections score 1.0, which is appropriate semantically but can
  raise macro scores on sparse profiles;
- exact entity matching may penalise harmless abbreviations or aliases;
- PII detection covers email and phone patterns but is not a complete privacy
  classifier;
- bias across profession, language, geography, gender expression, institution,
  and resume style has not yet been quantified;
- local Docling memory may limit horizontal scalability.

Ethically, parsed profiles should assist rather than automatically reject
candidates. Users need review and correction controls, transparent retention,
access control, deletion mechanisms, and monitoring for disparate impact.

## 12. Possible Improvements

- freeze the chosen prompt and execute the 52-resume held-out test once;
- repeat failed pairs without duplicating successful API calls;
- evaluate Gemini and Gemma on identical complete-profile inputs;
- capture provider usage, cost, retry-after values, and latency percentiles;
- add peak-memory measurement for Docling;
- use stratified reporting by scan quality, layout, page count, and category;
- add tolerant ontology-aware matching for skill aliases while retaining exact
  scores for auditability;
- add OCR confidence and fallback to direct vision when Docling text quality is
  low;
- evaluate a conditional router rather than forcing one strategy for all scans;
- expand gold annotation review, especially descriptions and dates;
- add bootstrap confidence intervals to paired metric differences;
- evaluate downstream recommendations with Precision@K, Recall@K, MAP, MRR, and
  nDCG once relevance-labelled ranking outputs are available.
