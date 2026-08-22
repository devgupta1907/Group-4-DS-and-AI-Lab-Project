import { useCallback, useState } from 'react';

import { toApiError } from '@shared/api/ApiError';

import { confirmJudge, searchJobs, selectQueries } from './api';
import type { JobDiscoveryResult, SearchPreferences } from './types';

export type JobDiscoveryPhase =
  | 'idle'
  | 'starting'
  | 'query_selection'
  | 'selecting'
  | 'judge_confirmation'
  | 'confirming'
  | 'done'
  | 'failed';

/**
 * Drives the whole job discovery run, including its two server-side
 * pauses (query_selection_gate, judge_confirmation_gate — see
 * backend/src/job_discovery_matching/internal/pipeline/graph.py).
 *
 * `phase` is this hook's own state, distinct from `result.status`: the
 * backend status only changes on a response; `phase` also covers the
 * in-flight moments ('starting', 'selecting', 'confirming') so the UI can
 * show the right loading copy for whichever call is currently running.
 */
export function useJobDiscovery() {
  const [phase, setPhase] = useState<JobDiscoveryPhase>('idle');
  const [result, setResult] = useState<JobDiscoveryResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const phaseForStatus = (status: JobDiscoveryResult['status']): JobDiscoveryPhase => {
    if (status === 'awaiting_query_selection') return 'query_selection';
    if (status === 'awaiting_judge_confirmation') return 'judge_confirmation';
    if (status === 'error') return 'failed';
    return 'done';
  };

  const start = useCallback(async (profileId: string, preferences: SearchPreferences) => {
    setPhase('starting');
    setError(null);
    try {
      const response = await searchJobs(profileId, preferences);
      setResult(response);
      setPhase(phaseForStatus(response.status));
    } catch (cause) {
      setError(toApiError(cause).message);
      setPhase('failed');
    }
  }, []);

  const submitQueries = useCallback(
    async (selectedQueries: string[]) => {
      if (!result?.run_id) return;
      setPhase('selecting');
      setError(null);
      try {
        const response = await selectQueries(result.run_id, selectedQueries);
        setResult(response);
        setPhase(phaseForStatus(response.status));
      } catch (cause) {
        setError(toApiError(cause).message);
        setPhase('failed');
      }
    },
    [result],
  );

  const submitJudgeConfirmation = useCallback(
    async (proceed: boolean, selectedJobUrls?: string[]) => {
      if (!result?.run_id) return;
      setPhase('confirming');
      setError(null);
      try {
        const response = await confirmJudge(result.run_id, proceed, selectedJobUrls);
        setResult(response);
        setPhase(phaseForStatus(response.status));
      } catch (cause) {
        setError(toApiError(cause).message);
        setPhase('failed');
      }
    },
    [result],
  );

  const reset = useCallback(() => {
    setPhase('idle');
    setResult(null);
    setError(null);
  }, []);

  return { phase, result, error, start, submitQueries, submitJudgeConfirmation, reset };
}
