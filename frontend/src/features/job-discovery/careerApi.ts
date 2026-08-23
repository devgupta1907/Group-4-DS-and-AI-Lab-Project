import { request } from '@shared/api/httpClient';

export type CareerRecommendation = {
  occupation_title: string;
  occupation_uri: string;
  confidence: 'high' | 'medium' | 'low';
  explanation: string;
  matched_evidence: string[];
};

export type CareerResult = {
  run_id: string;
  status: string;
  message: string;
  recommendations: CareerRecommendation[];
};

/**
 * Career recommendation only — no job discovery, no report.
 *
 * Lives in this feature rather than career-guidance so Rapid Search stays
 * self-contained and the report flow's own modules are untouched. It calls
 * the same endpoint career-guidance's report pipeline uses internally.
 */
export function recommendOccupations(profileId: string): Promise<CareerResult> {
  return request('/career/recommend', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ profile_id: profileId }),
  });
}

/**
 * Records which recommended directions the user kept.
 *
 * Must be called BEFORE searchJobs — job discovery reads the saved
 * selection off the latest recommendation run when it seeds `target_roles`
 * (see `selected_occupation_uris` in job_discovery_matching/service.py).
 *
 * Sends URIs rather than titles: the server resolves titles from the run
 * itself, so what gets searched always matches what was recommended.
 * An empty array clears the selection, which puts discovery back on its
 * default "top 2 recommendations" path.
 */
export function selectOccupations(
  runId: string,
  selectedUris: string[],
): Promise<CareerResult> {
  return request(`/career/recommendations/${runId}/select`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ selected_occupation_uris: selectedUris }),
  });
}
