"""The LangGraph pipeline state (internal — never leaves this package).

    candidate_json (from profile_mapper.from_parsed_resume(), 0 LLM calls)
      -> [Query Generator]    -> search_queries[]                       (1 LLM call)
      -> [Search Module]      -> job_urls[]                             (0 LLM calls)
      -> [Extraction Module]  -> raw_jobs[]  (crawl4ai + JSON-LD only)   (0 LLM calls)
      -> [Hard Filter]        -> filtered_jobs[]  (regex/rule-based)     (0 LLM calls)
      -> [Matching Module]    -> ranked_jobs[]  (BM25 + embeddings)      (0 LLM calls)
      -> [Judge Module]       -> final_jobs[]  (top N, ONE batched call) (1 LLM call)

Total: 2 LLM calls per run, regardless of how many jobs are discovered.

Unlike career-agent's original state, there is no `profile_ingest` node
and no `candidate_id` here: the candidate profile already has a stable
identity (`profile_id`, owned by resume_parsing) before this pipeline
ever runs, so there is nothing to ingest.
"""

from typing import Any, Optional, TypedDict
from uuid import UUID


class PipelineState(TypedDict, total=False):
    run_id: UUID
    profile_id: UUID

    candidate_json: dict[str, Any]  # from profile_mapper.from_parsed_resume()
    candidate_embedding: list[float]
    preferences: dict[str, Any]

    search_queries: list[str]

    job_urls: list[str]

    raw_jobs: list[dict[str, Any]]

    filtered_jobs: list[dict[str, Any]]

    ranked_jobs: list[dict[str, Any]]

    # Set by judge_confirmation_gate from the user's confirm-judge request:
    # True -> route_after_judge_confirmation sends the graph to
    # judge_module; False (or absent) -> hybrid_finalize_module instead.
    # Must be declared here or LangGraph drops it when merging node output
    # back into state -- it isn't a real channel otherwise, and the router
    # always reads it back as None regardless of what the user picked.
    proceed_to_judge: Optional[bool]

    # Set by judge_confirmation_gate from the user's confirm-judge request.
    # Non-empty -> judge_module restricts to these source_urls; None/empty
    # -> judge everything up to Cfg.TOP_N_JUDGED (original behaviour).
    selected_job_urls: Optional[list[str]]

    final_jobs: list[dict[str, Any]]

    error: Optional[str]
    progress: list[str]
    node_timings: list[dict[str, Any]]