import { request } from '@shared/api/httpClient';

import type { JobDiscoveryResult, SearchPreferences } from './types';

const BASE = '/jobs';

/**
 * Starts a job discovery run. Always returns status="awaiting_query_selection"
 * for a healthy run — query_generator runs, then query_selection_gate pauses
 * the pipeline before any Adzuna/SearXNG/crawl4ai call is spent. See
 * `useJobDiscovery.ts` for what happens with the response.
 */
export function searchJobs(
  profileId: string,
  preferences: SearchPreferences,
): Promise<JobDiscoveryResult> {
  return request(`${BASE}/search`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ profile_id: profileId, ...preferences }),
  });
}

/**
 * Resumes a run paused at "awaiting_query_selection" with the queries the
 * user picked (a subset of `generated_queries`, all of them, or edited
 * text). Runs through hybrid ranking and pauses AGAIN at
 * "awaiting_judge_confirmation" — this never returns a final result.
 */
export function selectQueries(
  runId: string,
  selectedQueries: string[],
): Promise<JobDiscoveryResult> {
  return request(`${BASE}/search/${runId}/select-queries`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ selected_queries: selectedQueries }),
  });
}

/**
 * Resumes a run paused at "awaiting_judge_confirmation". `proceed=true`
 * spends the LLM judge call (status becomes "ok" or "degraded_no_llm");
 * `proceed=false` finalizes with the same hybrid-ranked jobs already
 * shown, no LLM call (status becomes "hybrid_only"). Always terminal.
 *
 * `selectedJobUrls`, when given, judges only those jobs (matched on
 * `JobPostingView.source_url`) instead of every hybrid-ranked job —
 * omit it (or pass an empty/undefined value) to judge everything, same
 * as before this parameter existed.
 */
export function confirmJudge(
  runId: string,
  proceed: boolean,
  selectedJobUrls?: string[],
): Promise<JobDiscoveryResult> {
  return request(`${BASE}/search/${runId}/confirm-judge`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      proceed,
      ...(selectedJobUrls && selectedJobUrls.length > 0 ? { selected_job_urls: selectedJobUrls } : {}),
    }),
  });
}
