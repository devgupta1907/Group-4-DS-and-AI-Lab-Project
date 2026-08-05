# Prompt experimentation

This directory separates versioned prompt definitions from potentially
sensitive run data.

- `prompts/<name>/<version>.json`: immutable prompt text, change summary,
  rationale, parent version, acceptance criteria, and a content hash. Commit
  these files.
- `runs/<experiment>.jsonl`: the exact rendered prompt, output, model settings,
  latency, metrics, and notes for every call. This directory is git-ignored
  because rendered prompts may contain personal resume data.

Create a prompt version:

```python
from experimentation import PromptExperimentStore

store = PromptExperimentStore("experiments")
store.create_version(
    name="resume_parsing",
    version="v001",
    template="Extract this resume as JSON:\n\n{resume_text}",
    change_summary="Initial structured extraction prompt",
    rationale="Establish a reproducible baseline",
    acceptance_criteria=[
        "valid JSON",
        "no schema violations",
        "stable fields across the development set",
    ],
)
```

Never edit a version after creating it. Create `v002` with
`parent_version="v001"` and describe the exact change and the failure it fixes.
Use `store.diff_versions("resume_parsing", "v001", "v002")` to print the
exact line-by-line change for the report.

Render and record a run:

```python
prompt, exact_prompt = store.render(
    "resume_parsing", "v001", {"resume_text": resume_text}
)
result = llm.invoke(exact_prompt)
store.record_run(
    experiment="resume_parser_dev",
    prompt=prompt,
    rendered_prompt=exact_prompt,
    model="gemini-2.5-flash-lite",
    model_parameters={"temperature": 0.0},
    output=result.content,
    metrics={"schema_valid": True},
    notes="Development resume 07",
)
```

Each line in the run file is independent JSON, which makes it easy to load
with pandas and compare prompt versions, failures, latency, and metrics.

For real Gemini calls, use the instrumented shared client so recording also
happens when the API call fails:

```python
from services.llm_client import invoke_prompt_experiment

response = invoke_prompt_experiment(
    prompt_name="resume_parsing",
    prompt_version="v001",
    variables={"resume_text": resume_text},
    experiment="resume_parser_dev",
    model_parameters={"temperature": 0.0},
    metrics={"schema_valid": True},
    notes="Development resume 07",
)
```

Suggested revision workflow:

1. Keep `v001` as the baseline; never edit it.
2. Record the observed failure in the run's `notes`.
3. Create `v002`, linking `parent_version="v001"`, and state the exact prompt
   change and why it should fix that failure.
4. Run both versions on the same development examples.
5. Select a version using the declared acceptance criteria and captured
   metrics, not only visual inspection.

## Description-copy A/B experiment

`run_description_ab.py` selects five extractable resumes from the development
split and runs the same resumes through two prompts:

- `v001`: no explicit instruction about copying descriptions.
- `v002`: requires experience and project descriptions word-for-word.

It writes raw prompts and outputs under ignored `runs/`. It writes only
de-identified metrics and hashes to the Git-trackable
`results/description_copy_ab.jsonl`. This preserves the evidence if a laptop is
lost without putting resume PII into Git.

```bash
cd backend
.venv/bin/python experiments/run_description_ab.py
.venv/bin/python experiments/analyze_description_ab.py
```

The analysis command generates a CSV summary and a self-contained HTML report
with paired prompt comparisons, mean/median latency, schema success, verbatim
description rate, and exact recall against annotated descriptions.

### Description metric interpretation

The gold descriptions are incomplete/inconsistent, so prompt selection does not
optimize directly against them. The report uses:

- **Exact source rate:** fraction of returned descriptions found word-for-word
  in the OCR text. This is the strongest evidence for the copy requirement.
- **Source-window cosine / word F1:** near-verbatim alignment with the best
  similarly sized passage in the resume. These tolerate minor OCR differences.
- **Source fidelity:** `0.50 × exact rate + 0.25 × source cosine + 0.25 × word F1`.
- **Description count recall:** returned description count divided by annotated
  description count, capped at 1. This detects prompts that simply omit text.
- **Description score:** `0.70 × source fidelity + 0.30 × count recall`.
- **Gold cosine:** reported only as a diagnostic, not an acceptance criterion.

Latency is plotted separately because it is an efficiency metric and must not
be blended into extraction quality.

## Reproduce the Gemini 3.5 Flash experiment

This runs prompt `v002` against the same five pinned technology resumes:

```bash
cd backend
.venv/bin/python -u experiments/run_description_ab.py \
  --model gemini-3.5-flash \
  --versions v002 \
  --experiment gemini35_verbatim_raw \
  --results gemini35_verbatim.jsonl

.venv/bin/python experiments/analyze_model_comparison.py
```

The runner logs numbered progress to the terminal, retries rate-limit responses
after 5, 15 and 30 seconds, and does not record a run if all rate-limit retries
are exhausted. Repeated executions append new observations; analysis selects
the latest completed observation for each resume/model pair.

## Direct-vision versus Docling-text branch

The evaluation harness can send scanned resumes directly to the configured
model as page images, or run local Docling OCR/layout extraction first and send
the resulting Markdown to the same model:

```bash
cd backend

uv run python -m evals.run_eval \
  --variant baseline --input-strategy direct_vision --limit 5

uv run python -m evals.run_eval \
  --variant baseline --input-strategy docling_text --limit 5
```

Both runs use the ordinary LangSmith field/schema evaluators. They also append
de-identified local measurements to
`experiments/results/pipeline_timings.jsonl`: preprocessing, model and total
latency; input kind and size; schema validity; coverage; success/error type;
and content hashes. Raw OCR text and candidate profiles are never written to
that metrics file.

Production selects the same branch through:

```dotenv
RESUME_SCANNED_PDF_STRATEGY=direct_vision  # or docling_text
```

Born-digital PDFs and DOCX resumes still use native text extraction. The flag
only changes the handling of scanned/image-only PDFs.

## Report directory

```text
reports/
├── gemma4_prompt_ab/       # Baseline prompt versus verbatim prompt
├── gemini35_verbatim/      # Gemini per-resume plots and redacted sample JSON
└── model_comparison/       # Gemma 4 versus Gemini 3.5 on prompt v002
```

Raw prompts and model outputs remain under ignored `runs/`. Only de-identified
metrics, plots, and the explicitly redacted sample profile are suitable for Git.
