import { useCallback, useState } from 'react';

import { toApiError } from '@shared/api/ApiError';

import { updateProfile } from '../api/resumeParsingApi';
import type { CandidateProfile, ProfileRecord } from '../types/parsedProfile';

/** '' -> null for every optional string field the schema stores as `null`
    when absent. Arrays (skills, links, technologies, job_titles) are left
    alone — an empty array is already the correct "none" representation
    for those, there's no '' equivalent to clean up. */
function normalizeProfile(draft: CandidateProfile): CandidateProfile {
  const blankToNull = (value: string | null) => (value?.trim() ? value : null);

  return {
    ...draft,
    contact: {
      ...draft.contact,
      name: blankToNull(draft.contact.name),
      location: blankToNull(draft.contact.location),
    },
    education: draft.education.map((entry) => ({
      ...entry,
      degree: blankToNull(entry.degree),
      field: blankToNull(entry.field),
      institution: blankToNull(entry.institution),
      start_year: blankToNull(entry.start_year),
      end_year: blankToNull(entry.end_year),
    })),
    experience: draft.experience.map((entry) => ({
      ...entry,
      job_title: blankToNull(entry.job_title),
      company: blankToNull(entry.company),
      location: blankToNull(entry.location),
      start_date: blankToNull(entry.start_date),
      end_date: blankToNull(entry.end_date),
      description: blankToNull(entry.description),
    })),
    projects: draft.projects.map((entry) => ({
      ...entry,
      name: blankToNull(entry.name),
      description: blankToNull(entry.description),
    })),
    certifications: draft.certifications.map((entry) => ({
      ...entry,
      name: blankToNull(entry.name),
      issuer: blankToNull(entry.issuer),
      year: blankToNull(entry.year),
    })),
  };
}

export type ProfileEditor = {
  isEditing: boolean;
  /** The working copy while editing; null when not in edit mode. */
  draft: CandidateProfile | null;
  isSaving: boolean;
  error: string | null;
  startEditing: () => void;
  cancelEditing: () => void;
  updateDraft: (updater: (draft: CandidateProfile) => CandidateProfile) => void;
  save: () => Promise<void>;
};

/**
 * Owns the "edit the parsed profile" flow for one `ProfileRecord`: enter
 * edit mode with a working copy, mutate that copy field-by-field via
 * `updateDraft`, then PATCH the whole thing back on `save()`.
 *
 * `onSaved` is how the caller learns the save succeeded — typically
 * `useResumeUpload`'s `setRecord`, so the rest of the page picks up the
 * edited profile without a re-fetch.
 */
export function useProfileEditor(
  record: ProfileRecord | null,
  onSaved: (record: ProfileRecord) => void,
): ProfileEditor {
  const [draft, setDraft] = useState<CandidateProfile | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const startEditing = useCallback(() => {
    if (!record) return;
    setDraft(structuredClone(record.profile));
    setError(null);
  }, [record]);

  const cancelEditing = useCallback(() => {
    setDraft(null);
    setError(null);
  }, []);

  const updateDraft = useCallback((updater: (draft: CandidateProfile) => CandidateProfile) => {
    setDraft((prev) => (prev ? updater(prev) : prev));
  }, []);

  const save = useCallback(async () => {
    if (!record || !draft) return;
    setIsSaving(true);
    setError(null);
    try {
      const updated = await updateProfile(record.id, normalizeProfile(draft));
      onSaved(updated);
      setDraft(null);
    } catch (cause) {
      setError(toApiError(cause).message);
    } finally {
      setIsSaving(false);
    }
  }, [record, draft, onSaved]);

  return {
    isEditing: draft !== null,
    draft,
    isSaving,
    error,
    startEditing,
    cancelEditing,
    updateDraft,
    save,
  };
}
