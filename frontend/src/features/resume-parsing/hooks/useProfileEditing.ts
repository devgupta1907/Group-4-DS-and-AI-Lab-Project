import { useCallback, useState } from 'react';

import type { ProfileRecord } from '../types/parsedProfile';

import { useProfileEditor, type ProfileEditor } from './useProfileEditor';
import { useSaveProfile } from './useSaveProfile';

export type ProfileEditing = {
  isEditing: boolean;
  editor: ProfileEditor;
  saving: boolean;
  error: string | null;
  start: () => void;
  cancel: () => void;
  save: () => Promise<void>;
};

/**
 * Combines local-edit state (`useProfileEditor`) with the save call
 * (`useSaveProfile`) into the handful of things a review screen needs: whether
 * it's in edit mode, and the three actions that move it in and out.
 */
export function useProfileEditing(
  record: ProfileRecord,
  onSaved: (record: ProfileRecord) => void,
): ProfileEditing {
  const [isEditing, setIsEditing] = useState(false);
  const editor = useProfileEditor(record.profile);
  const { saving, error, save: saveProfile, clearError } = useSaveProfile();

  const start = useCallback(() => {
    editor.reset(record.profile);
    clearError();
    setIsEditing(true);
  }, [clearError, editor, record.profile]);

  const cancel = useCallback(() => {
    editor.reset(record.profile);
    clearError();
    setIsEditing(false);
  }, [clearError, editor, record.profile]);

  const save = useCallback(async () => {
    const saved = await saveProfile(record.id, editor.profile);
    if (saved) {
      onSaved(saved);
      setIsEditing(false);
    }
  }, [editor.profile, onSaved, record.id, saveProfile]);

  return { isEditing, editor, saving, error, start, cancel, save };
}
