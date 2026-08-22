import { useCallback, useState } from 'react';

import { blankProfile } from '../blankProfile';
import type { CandidateProfile } from '../types/parsedProfile';

export type ManualProfile = {
  draft: CandidateProfile;
  updateDraft: (updater: (draft: CandidateProfile) => CandidateProfile) => void;
  reset: () => void;
};

/**
 * Owns the working copy for manual profile entry — the same
 * `(draft, updateDraft)` shape `useProfileEditor` gives the edit flow for
 * an already-parsed profile, so `EditableProfileView` renders either one
 * without caring which produced it.
 *
 * Pass `initialProfile` to start from a previously-submitted manual
 * profile (the "Edit details" path back from `ManualProfileView`) instead
 * of a blank one.
 */
export function useManualProfile(initialProfile?: CandidateProfile): ManualProfile {
  const [draft, setDraft] = useState<CandidateProfile>(() => initialProfile ?? blankProfile());

  const updateDraft = useCallback((updater: (draft: CandidateProfile) => CandidateProfile) => {
    setDraft((prev) => updater(prev));
  }, []);

  const reset = useCallback(() => {
    setDraft(blankProfile());
  }, []);

  return { draft, updateDraft, reset };
}
