import { useCallback, useState } from 'react';

import { toApiError } from '@shared/api/ApiError';
import { request } from '@shared/api/httpClient';

export type FeedbackReason = { value: string; label: string };

export type FeedbackRecord = {
  feedback_id: string;
  rating: number;
  reasons: string[];
  comment: string;
  profile_id: string | null;
  created_at: string;
};

/** Served by the backend so the option list is not duplicated here. */
export function fetchReasons(): Promise<FeedbackReason[]> {
  return request('/feedback/reasons');
}

export function submitFeedback(body: {
  rating: number;
  reasons: string[];
  comment: string;
  profile_id?: string | null;
}): Promise<FeedbackRecord> {
  return request('/feedback', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

export function useFeedback() {
  const [reasons, setReasons] = useState<FeedbackReason[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [record, setRecord] = useState<FeedbackRecord | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Called when the dialog opens rather than on mount, so a user who never
  // opens it costs no request.
  const loadReasons = useCallback(async () => {
    if (reasons.length > 0) return;
    try {
      setReasons(await fetchReasons());
    } catch {
      // The reason chips are optional; a rating alone is still a valid
      // submission, so a failure here degrades rather than blocks.
      setReasons([]);
    }
  }, [reasons.length]);

  const submit = useCallback(
    async (rating: number, selected: string[], comment: string, profileId?: string | null) => {
      setSubmitting(true);
      setError(null);
      try {
        setRecord(await submitFeedback({
          rating,
          reasons: selected,
          comment,
          profile_id: profileId ?? null,
        }));
      } catch (cause) {
        setError(toApiError(cause).message);
      } finally {
        setSubmitting(false);
      }
    },
    [],
  );

  const reset = useCallback(() => {
    setRecord(null);
    setError(null);
  }, []);

  return { reasons, loadReasons, submit, submitting, record, error, reset };
}
