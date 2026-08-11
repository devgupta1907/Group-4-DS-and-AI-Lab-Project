# career-agent evals

Four `promptfoo` evals covering every tunable part of the pipeline, plus a
script that ranks the results and picks a winner per eval.

```
evals/
  promptfoo/
    prompts/          # eval 1: LLM prompt wording variants (query_generator + judge_batch)
    search_crawl/      # eval 2: SearXNG + Crawl4AI parameter sweep, zero LLM calls
    ranking/            # eval 3: BM25/embedding hybrid weight sweep, recall@10/precision@10/ndcg@10
  scripts/
    run_all.sh           # runs all 4 evals + aggregates
    aggregate_results.py # ranks configs, writes best_config.json + leaderboard_*.md
  results/              # output — gitignore this in practice
```

## Quick start

```bash
cd evals/scripts
./run_all.sh
```

That's it — it runs in **mock mode** by default (`EVAL_MOCK=1`), so it needs
no API key, no SearXNG, no Postgres/Redis, no downloaded embedding model.
Every provider falls back to a deterministic synthetic response so you can
validate the harness, the assertions, and the aggregation logic for free.

Mock-mode numbers are **harness smoke tests, not real quality signal** —
see "Running for real" below once you're ready to make actual decisions.

Output:
- `results/leaderboard_*.md` — one ranked table per eval
- `results/best_config.json` — the winning label + its scores per eval
- `results/summary.md` — one-line rollup across all 4

## The 4 evals, and why LLM calls are kept low

| Eval | What it sweeps | LLM calls | Metrics |
|---|---|---|---|
| `prompts/query_generator...` | 3 prompt wordings × 4 candidates | **12** (real mode) | schema validity, query diversity, latency |
| `prompts/judge...` | 2 prompt wordings × 2 job-batches | **4** (real mode) | schema validity, score/recommendation calibration, latency |
| `search_crawl/` | 5 param sets × 5 queries | **0** | unique URLs found, crawl success rate, latency |
| `ranking/` | 7 weight configs × 3 labeled candidates | **0** | recall@10, precision@10, ndcg@10, latency |

This mirrors production: `matching_module.py` (ranking) and
`search_module.py`/`crawler_service.py` never call an LLM either, so those
two evals — the ones with the largest test×config matrix — cost nothing to
run repeatedly while you tune weights or timeouts. The only LLM spend is in
the 2 prompt evals, and even there:

- **No `llm-rubric` / model-graded assertions anywhere.** Every assertion is
  a plain Python function checking JSON schema, value ranges, and internal
  consistency (`validators.py` in each eval dir). A model-graded assertion
  would double the call count (1 to generate + 1 to grade); this design
  keeps it at exactly `variants × test_cases`.
- `cache: true` in every config, so re-running while you edit `validators.py`
  doesn't re-spend already-graded calls.
- Small, deliberately-scoped test sets (4 and 2 cases) rather than sweeping
  dozens of candidates — the prompt-quality signal from schema/calibration
  checks saturates quickly; you don't need hundreds of calls to see it.

## Running for real

**Prompt evals** (`evals/promptfoo/prompts/`):
```bash
export EVAL_MOCK=0
export OPENROUTER_API_KEY=sk-or-...
cd evals/promptfoo/prompts
promptfoo eval -c query_generator.promptfooconfig.yaml -o ../../results/prompts_query_generator.json
promptfoo eval -c judge.promptfooconfig.yaml -o ../../results/prompts_judge.json
```

**Search + crawl eval**: needs SearXNG reachable (`docker compose up searxng
redis`) and `backend/` importable (its dependencies installed — the provider
tries `from app.services import searxng_client, crawler_service` and falls
back to mock automatically if that import or a health check fails). Easiest
path is running it from inside the backend container:
```bash
docker compose exec backend bash
cd /app/evals/promptfoo/search_crawl   # adjust to your mount path
EVAL_MOCK=0 promptfoo eval -c promptfooconfig.yaml -o ../../results/search_crawl.json
```

**Ranking eval**: BM25 scoring works anywhere (`rank_bm25` is a light pure-Python
dependency). Real embeddings need `sentence-transformers` + the
`BAAI/bge-base-en-v1.5` weights downloaded — run this from the backend env
too, or `pip install sentence-transformers` locally and let it download the
model on first use:
```bash
cd evals/promptfoo/ranking
EVAL_MOCK=0 promptfoo eval -c promptfooconfig.yaml -o ../../results/ranking.json
```

Then, regardless of which evals you ran for real vs mock:
```bash
cd evals/scripts
python3 aggregate_results.py
```

## Editing / extending

- **Add a prompt variant**: drop a new `.txt` file in
  `prompts/prompts/` (uses `SYSTEM: ... USER: ...` + `{{var}}` nunjucks
  syntax) and add it to the `prompts:` list in the relevant
  `*.promptfooconfig.yaml`.
- **Add a parameter combo** (search/crawl or ranking): add another
  `providers:` entry with a new `label` and `config` block — same script,
  different config, shows up as a new leaderboard row.
- **Add a test case**: add a row to the relevant `tests/*.yaml`.
- **Change what "best" means**: edit the `*_WEIGHTS` dicts at the top of
  `scripts/aggregate_results.py`. Composite score = weighted sum of quality
  metrics minus a latency penalty (latency is min-max normalised across that
  eval's rows so it's comparable to 0-1 quality scores).
- **Apply the winner**: `results/best_config.json` tells you which
  label won each eval — cross-reference its `config:` block in the
  corresponding `promptfooconfig.yaml` and copy the values into
  `backend/app/config.py` (`bm25_weight`, `embedding_weight`,
  `top_k_ranked`, `max_job_urls`, `crawl_concurrency`, `crawl_timeout_ms`)
  or into the winning prompt file's content in `backend/app/pipeline/prompts.py`.
  This is left as a manual step on purpose — promoting a config to
  production shouldn't be silent.

## Ranking eval data: the golden dataset

`ranking/data/eval_dataset.json` is generated from a real, hand-labeled
golden dataset (`Job_Matching_Golden_Dataset.xlsx`: 86 candidates x 10
synthetic-but-realistic jobs each, spanning 5 designed match tiers, with
a documented `ground_truth_rule_score` formula) — not the placeholder data
this eval originally shipped with. To regenerate it (e.g. from an updated
version of the workbook):

```bash
pip install openpyxl --break-system-packages
cd evals/scripts
python3 build_ranking_dataset_from_xlsx.py /path/to/Job_Matching_Golden_Dataset.xlsx
#   --split dev   # 34 candidates, for iterating on weights
#   --split test  # 52 candidates, for a final check
#   --split all   # default: all 86
```

This also regenerates `ranking/tests/candidates.yaml` to match.

**Metrics changed to fit this dataset.** Each candidate only has 10 jobs
(not the 15 the original synthetic set used), which makes recall@10 /
precision@10 degenerate — the "top 10 of a 10-item pool" is just the
whole pool, so those two would score identically regardless of ranking
quality. The ranking eval now reports what the dataset's own README
recommends instead:
- **precision@5** — overlap with `ground_truth_top5` (a fixed 5-of-10 set per candidate)
- **ndcg@10** — against the continuous `ground_truth_rule_score`, not a bucketed label
- **spearman_correlation** — full rank-order agreement across all 10 jobs; this is the
  most sensitive of the three when there are only 10 items to rank, so watch it most closely

## Requirements

- Node.js + `npm install -g promptfoo` (tested against `promptfoo@0.121`)
- Python 3.10+ (stdlib only for `prompts/` and `search_crawl/` mock mode;
  `rank_bm25` for `ranking/`, `pip install rank_bm25 --break-system-packages`)
- For real (non-mock) runs: whatever `backend/requirements.txt` needs
  (crawl4ai/Playwright, sentence-transformers, a running SearXNG + Redis,
  and an OpenRouter API key)
