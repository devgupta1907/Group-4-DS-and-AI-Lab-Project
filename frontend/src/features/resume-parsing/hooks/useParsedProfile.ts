import { useCallback, useEffect, useState } from 'react';

import { toApiError } from '@shared/api/ApiError';

import { fetchProfile } from '../api/resumeParsingApi';
import type { ProfileRecord } from '../types/parsedProfile';

type ParsedProfileState = {
  record: ProfileRecord | null;
  isLoading: boolean;
  error: string | null;
};

/**
 * Loads a previously persisted profile by id.
 *
 * Used to re-open a profile after a reload, when the SSE stream that produced
 * it is long gone. Pass `null` to stay idle.
 */
export function useParsedProfile(profileId: string | null) {
  const [state, setState] = useState<ParsedProfileState>({
    record: null,
    isLoading: false,
    error: null,
  });

  const load = useCallback(async (id: string, signal: { cancelled: boolean }) => {
    setState({ record: null, isLoading: true, error: null });
    try {
      const record = await fetchProfile(id);
      if (!signal.cancelled) setState({ record, isLoading: false, error: null });
    } catch (cause) {
      if (!signal.cancelled) {
        setState({ record: null, isLoading: false, error: toApiError(cause).message });
      }
    }
  }, []);

  useEffect(() => {
    if (profileId === null) {
      setState({ record: null, isLoading: false, error: null });
      return;
    }
    const signal = { cancelled: false };
    void load(profileId, signal);
    return () => {
      signal.cancelled = true;
    };
  }, [profileId, load]);

  return state;
}
