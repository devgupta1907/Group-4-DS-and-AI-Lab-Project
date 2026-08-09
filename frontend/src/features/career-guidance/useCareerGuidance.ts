import { useCallback, useState } from 'react';

import { toApiError } from '@shared/api/ApiError';

import { generateReport } from './api';
import type { CareerReport, SearchPreferences } from './types';

export type AnalysisStatus = 'idle' | 'reporting' | 'complete' | 'failed';

/**
 * Runs the full analysis and holds the result.
 *
 * An earlier version split this into two phases — occupations first, then the
 * report — so the user saw something within ten seconds. That was dropped once
 * the intermediate screen came down to a list of bare occupation titles: not
 * enough to decide anything on, and an extra click before the thing they
 * actually asked for. The occupations still appear in the report, where they
 * carry their supporting evidence.
 *
 * The backend still runs recommendation before job discovery internally, and
 * POST /api/career/recommend remains available for callers that want the
 * occupations alone.
 */
export function useCareerGuidance() {
  const [status, setStatus] = useState<AnalysisStatus>('idle');
  const [report, setReport] = useState<CareerReport | null>(null);
  const [error, setError] = useState<string | null>(null);

  const buildReport = useCallback(
    async (profileId: string, preferences: SearchPreferences) => {
      setStatus('reporting');
      setError(null);
      try {
        setReport(await generateReport(profileId, preferences));
        setStatus('complete');
      } catch (cause) {
        setError(toApiError(cause).message);
        setStatus('failed');
      }
    },
    [],
  );

  const reset = useCallback(() => {
    setStatus('idle');
    setReport(null);
    setError(null);
  }, []);

  return { status, report, error, buildReport, reset };
}
