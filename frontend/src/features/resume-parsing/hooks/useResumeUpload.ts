import { useCallback, useEffect, useRef, useState } from 'react';

import { toApiError } from '@shared/api/ApiError';

import { parseResume } from '../api/resumeParsingApi';
import type { ParseStage, ProfileRecord } from '../types/parsedProfile';

export type UploadStatus = 'idle' | 'parsing' | 'succeeded' | 'failed';

export type UploadFailure = {
  code: string;
  message: string;
};

export type ResumeUpload = {
  status: UploadStatus;
  /** The stage the server most recently reported, or null before it starts. */
  stage: ParseStage | null;
  /** Free-text context for the current stage — page count, model name, etc. */
  detail: string | null;
  /** Every stage seen so far, so the stepper can mark them complete. */
  completedStages: ParseStage[];
  record: ProfileRecord | null;
  error: UploadFailure | null;
  file: File | null;
  upload: (file: File) => void;
  cancel: () => void;
  reset: () => void;
};

/** Everything the hook tracks, minus the callbacks it returns alongside it. */
type UploadState = Omit<ResumeUpload, 'upload' | 'cancel' | 'reset'>;

const INITIAL: UploadState = {
  status: 'idle',
  stage: null,
  detail: null,
  completedStages: [],
  record: null,
  error: null,
  file: null,
};

/**
 * Owns the whole upload lifecycle: the SSE stream, the stage timeline, the
 * terminal result and cancellation.
 *
 * Components render what this returns and never touch the stream themselves.
 */
export function useResumeUpload(): ResumeUpload {
  const [state, setState] = useState<UploadState>(INITIAL);
  const abortRef = useRef<AbortController | null>(null);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      abortRef.current?.abort();
    };
  }, []);

  const cancel = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setState((prev) => (prev.status === 'parsing' ? { ...INITIAL, file: prev.file } : prev));
  }, []);

  const reset = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setState(INITIAL);
  }, []);

  const upload = useCallback((file: File) => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setState({ ...INITIAL, status: 'parsing', file });

    void (async () => {
      try {
        for await (const event of parseResume(file, controller.signal)) {
          if (!mountedRef.current || controller.signal.aborted) return;

          if (event.type === 'stage') {
            setState((prev) => ({
              ...prev,
              stage: event.stage,
              detail: event.detail,
              completedStages: prev.completedStages.includes(event.stage)
                ? prev.completedStages
                : [...prev.completedStages, event.stage],
            }));
          } else if (event.type === 'profile') {
            setState((prev) => ({ ...prev, status: 'succeeded', record: event.record }));
          } else {
            setState((prev) => ({
              ...prev,
              status: 'failed',
              error: { code: event.code, message: event.message },
            }));
          }
        }
      } catch (cause) {
        if (!mountedRef.current || controller.signal.aborted) return;
        const error = toApiError(cause);
        setState((prev) => ({
          ...prev,
          status: 'failed',
          error: { code: error.code, message: error.message },
        }));
      }
    })();
  }, []);

  return { ...state, upload, cancel, reset };
}
