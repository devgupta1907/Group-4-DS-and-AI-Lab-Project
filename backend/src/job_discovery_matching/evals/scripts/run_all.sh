#!/usr/bin/env bash
# Runs all 4 career-agent promptfoo evals, then aggregates + ranks the
# results into evals/results/best_config.json + leaderboard_*.md.
#
# Usage:
#   ./run_all.sh              # mock mode (no API key, no infra, zero spend)
#   EVAL_MOCK=0 ./run_all.sh  # real mode — needs OPENROUTER_API_KEY for the
#                              # prompt evals, and SearXNG reachable + this
#                              # run from an env with backend/requirements.txt
#                              # installed for real search/crawl/embedding numbers.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EVALS_DIR="$(dirname "$SCRIPT_DIR")"
RESULTS_DIR="$EVALS_DIR/results"
mkdir -p "$RESULTS_DIR"

export EVAL_MOCK="${EVAL_MOCK:-1}"
echo "EVAL_MOCK=$EVAL_MOCK"
if [ "$EVAL_MOCK" = "1" ]; then
  echo "(mock mode — zero LLM calls, zero external services required)"
fi

# Default: always fresh (--no-cache), so a combined run never mixes in
# stale results. Set NO_CACHE=0 to reuse promptfoo's cache instead — useful
# if you already ran an eval individually and don't want to re-spend LLM
# calls on prompts/* just to fold it into a combined run.
CACHE_FLAG="--no-cache"
if [ "${NO_CACHE:-1}" = "0" ]; then
  CACHE_FLAG=""
  echo "NO_CACHE=0 — reusing promptfoo's cache where available"
fi
echo

run_eval () {
  local dir="$1" config="$2" out="$3"
  echo "=== $out ==="
  (cd "$EVALS_DIR/promptfoo/$dir" && promptfoo eval -c "$config" -o "$RESULTS_DIR/$out" $CACHE_FLAG)
  echo
}

run_eval "ranking"      "promptfooconfig.yaml"               "ranking.json"
run_eval "search_crawl" "promptfooconfig.yaml"                "search_crawl.json"
run_eval "prompts"      "query_generator.promptfooconfig.yaml" "prompts_query_generator.json"
run_eval "prompts"      "judge.promptfooconfig.yaml"           "prompts_judge.json"

echo "=== Aggregating ==="
python3 "$SCRIPT_DIR/aggregate_results.py" --results-dir "$RESULTS_DIR"
