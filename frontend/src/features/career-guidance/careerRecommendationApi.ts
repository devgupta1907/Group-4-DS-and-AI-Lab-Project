import { request } from '@shared/api/httpClient';

import type { CareerResult } from './types';

/**
 * Runs career recommendation ALONE — retrieve, re-rank, explain — against
 * a stored profile. Distinct from `generateReport()` in api.ts, which
 * chains career recommendation -> job discovery -> narrative synthesis
 * into one combined report; this hits the standalone endpoint and returns
 * just the ranked occupations.
 */
export function recommendCareers(profileId: string): Promise<CareerResult> {
  return request('/career/recommend', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ profile_id: profileId }),
  });
}

/**
 * Records which recommended occupation(s) the candidate picked, against the
 * run that produced them. Job Discovery reads this back server-side and
 * searches on those roles specifically instead of falling back to the top
 * 2 recommendations automatically. Pass an empty array to clear a
 * previous selection.
 */
export async function selectOccupations(runId: string, occupationUris: string[]): Promise<void> {
  await request(`/career/recommendations/${runId}/select`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ occupation_uris: occupationUris }),
  });
}
