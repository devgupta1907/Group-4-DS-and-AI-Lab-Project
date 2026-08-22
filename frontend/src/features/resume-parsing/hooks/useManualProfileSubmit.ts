import { useCallback, useState } from 'react';

import { toApiError } from '@shared/api/ApiError';

import { submitManualProfile } from '../api/resumeParsingApi';
import type { CandidateProfile, ProfileRecord } from '../types/parsedProfile';

export type ManualProfileSubmit = {
  isSubmitting: boolean;
  error: string | null;
  /** Resolves to the saved record, or `null` if the request failed (see
      `error` for why) — callers don't need a try/catch of their own. */
  submit: (profile: CandidateProfile) => Promise<ProfileRecord | null>;
};

/**
 * Owns the "save a manually-entered profile" request: one POST, no
 * streaming (unlike `useResumeUpload`, there is no pipeline to report
 * progress on — the profile is already fully formed).
 */
export function useManualProfileSubmit(): ManualProfileSubmit {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = useCallback(async (profile: CandidateProfile) => {
    setIsSubmitting(true);
    setError(null);
    try {
      return await submitManualProfile(profile);
    } catch (cause) {
      setError(toApiError(cause).message);
      return null;
    } finally {
      setIsSubmitting(false);
    }
  }, []);

  return { isSubmitting, error, submit };
}
