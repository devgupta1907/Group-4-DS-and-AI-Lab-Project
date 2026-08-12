import { useCallback, useEffect, useState } from 'react';

import { useFeedback } from './feedbackApi';
import { FeedbackForm } from './FeedbackForm';
import styles from './FeedbackWidget.module.css';

type FeedbackWidgetProps = {
  /** Attaches the response to a run when there is one. Optional by design. */
  profileId?: string | null;
};

/**
 * One button, one dialog.
 *
 * The button sits on every page rather than only after a report, because the
 * people most worth hearing from include those who gave up before the end.
 */
export function FeedbackWidget({ profileId }: FeedbackWidgetProps) {
  const [open, setOpen] = useState(false);
  const [rating, setRating] = useState<number | null>(null);
  const [selected, setSelected] = useState<string[]>([]);
  const [comment, setComment] = useState('');
  const feedback = useFeedback();

  useEffect(() => {
    if (open) void feedback.loadReasons();
  }, [open, feedback]);

  // Escape closes, which is expected of any modal and cheap to support.
  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => { if (event.key === 'Escape') setOpen(false); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open]);

  const toggleReason = useCallback((value: string) => {
    setSelected((current) =>
      current.includes(value) ? current.filter((r) => r !== value) : [...current, value],
    );
  }, []);

  const close = useCallback(() => {
    setOpen(false);
    setRating(null);
    setSelected([]);
    setComment('');
    feedback.reset();
  }, [feedback]);

  const send = useCallback(() => {
    if (rating === null) return;
    void feedback.submit(rating, selected, comment, profileId);
  }, [comment, feedback, profileId, rating, selected]);

  return (
    <>
      <button className={styles.launcher} type="button" onClick={() => setOpen(true)}>
        Give feedback
      </button>

      {open && (
        <div className={styles.overlay} role="dialog" aria-modal="true" aria-labelledby="fb-title">
          <div className={styles.dialog}>
            {feedback.record ? (
              <div className={styles.thanks}>
                <p className={styles.thanksMark} aria-hidden="true">✓</p>
                <h2 id="fb-title">Thank you</h2>
                <p>Your feedback has been recorded.</p>
                <p className={styles.refId}>Reference {feedback.record.feedback_id}</p>
                <button className="primary-action" type="button" onClick={close}>Close</button>
              </div>
            ) : (
              <FeedbackForm
                rating={rating}
                onRate={setRating}
                reasons={feedback.reasons}
                selected={selected}
                onToggleReason={toggleReason}
                comment={comment}
                onComment={setComment}
                error={feedback.error}
                submitting={feedback.submitting}
                onSubmit={send}
                onCancel={close}
              />
            )}
          </div>
        </div>
      )}
    </>
  );
}
