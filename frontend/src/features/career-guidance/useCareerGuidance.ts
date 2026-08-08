import { useCallback, useState } from 'react';

import { toApiError } from '@shared/api/ApiError';

import { generateReport } from './api';
import type { CareerReport, SearchPreferences } from './types';

export type AnalysisStatus = 'idle' | 'analysing' | 'reporting' | 'complete' | 'failed';

export function useCareerGuidance() {
  const [status, setStatus] = useState<AnalysisStatus>('idle');
  const [report, setReport] = useState<CareerReport | null>(null);
  const [error, setError] = useState<string | null>(null);

  const analyse = useCallback(
    async (profileId: string, preferences: SearchPreferences) => {
      setStatus('analysing');
      setError(null);
      try {
        const result = await generateReport(profileId, preferences);
        setReport(result);
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

  return { status, report, error, analyse, reset };
}
