import { useCallback, useState } from 'react';

import { toApiError } from '@shared/api/ApiError';

import { recommendCareers, selectOccupations as selectOccupationsApi } from './careerRecommendationApi';
import type { CareerResult } from './types';

export type CareerRecommendationStatus = 'idle' | 'loading' | 'complete' | 'failed';

/**
 * Owns the standalone career-recommendation run — separate from
 * `useCareerGuidance`, which drives the combined report (career
 * recommendation + job discovery + narrative). This hook only ever calls
 * `POST /api/career/recommend`; there is nothing to poll or resume, the
 * whole run completes in one request.
 *
 * Also owns which occupation(s) the candidate picked from that run —
 * `selectedUris`. A candidate can be open to more than one direction, so
 * this is a set, not a single value: `toggleOccupation` adds or removes
 * one uri and persists the resulting set server-side (`POST
 * /career/recommendations/{run_id}/select`), so Job Discovery can read it
 * back and search on exactly those roles instead of guessing from the top
 * of the ranked list.
 */
export function useCareerRecommendation() {
  const [status, setStatus] = useState<CareerRecommendationStatus>('idle');
  const [result, setResult] = useState<CareerResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selectedUris, setSelectedUris] = useState<string[]>([]);

  const run = useCallback(async (profileId: string) => {
    setStatus('loading');
    setError(null);
    setSelectedUris([]);
    try {
      setResult(await recommendCareers(profileId));
      setStatus('complete');
    } catch (cause) {
      setError(toApiError(cause).message);
      setStatus('failed');
    }
  }, []);

  /**
   * Optimistic: the UI reflects the toggle immediately, and rolls back if
   * the server rejects it (e.g. a stale run_id). A silently-failed
   * selection would send Job Discovery down the wrong role(s) without the
   * candidate knowing, which is worse than a visible revert.
   */
  const toggleOccupation = useCallback(
    async (occupationUri: string) => {
      if (!result?.run_id) return;
      const previous = selectedUris;
      const next = previous.includes(occupationUri)
        ? previous.filter((uri) => uri !== occupationUri)
        : [...previous, occupationUri];
      setSelectedUris(next);
      try {
        await selectOccupationsApi(result.run_id, next);
      } catch (cause) {
        setSelectedUris(previous);
        setError(toApiError(cause).message);
      }
    },
    [result, selectedUris],
  );

  const reset = useCallback(() => {
    setStatus('idle');
    setResult(null);
    setError(null);
    setSelectedUris([]);
  }, []);

  return { status, result, error, selectedUris, run, toggleOccupation, reset };
}
