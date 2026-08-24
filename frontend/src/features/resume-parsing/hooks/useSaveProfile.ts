import { useCallback, useState } from 'react';

import { toApiError } from '@shared/api/ApiError';

import { updateProfile } from '../api/resumeParsingApi';
import type { CandidateProfile, ProfileRecord } from '../types/parsedProfile';

export type SaveProfile = {
  saving: boolean;
  error: string | null;
  /** Resolves with the saved record, or `null` if the save failed. */
  save: (profileId: string, profile: CandidateProfile) => Promise<ProfileRecord | null>;
  clearError: () => void;
};

/**
 * Owns the PUT call for a profile edit: loading state, one readable error
 * message, nothing else. `EditProfileForm` stays presentational; this is
 * where the network lives, same split as `useResumeUpload` for the parse.
 */
export function useSaveProfile(): SaveProfile {
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const save = useCallback(
    async (profileId: string, profile: CandidateProfile): Promise<ProfileRecord | null> => {
      setSaving(true);
      setError(null);
      try {
        return await updateProfile(profileId, profile);
      } catch (cause) {
        setError(toApiError(cause).message);
        return null;
      } finally {
        setSaving(false);
      }
    },
    [],
  );

  const clearError = useCallback(() => setError(null), []);

  return { saving, error, save, clearError };
}
