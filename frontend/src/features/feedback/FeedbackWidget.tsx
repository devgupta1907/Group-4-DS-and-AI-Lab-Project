import { useCallback, useEffect, useState } from 'react';

import { useFeedback } from './feedbackApi';
import styles from './FeedbackWidget.module.css';

type FeedbackWidgetProps = {
  /** Attaches the response to a run when there is one. Optional by design. */
  profileId?: string | null;
};

const SCALE = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10];

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
              <>
                <p className="eyebrow">Your feedback</p>
                <h2 id="fb-title">How useful was this?</h2>

                <fieldset className={styles.scaleGroup}>
                  <legend className={styles.legend}>Rating out of 10</legend>
                  <div className={styles.scale}>
                    {SCALE.map((score) => (
                      <button
                        key={score}
                        type="button"
                        aria-pressed={rating === score}
                        className={`${styles.scoreBtn} ${rating === score ? styles.scoreOn : ''}`}
                        onClick={() => setRating(score)}
                      >
                        {score}
                      </button>
                    ))}
                  </div>
                  <div className={styles.scaleEnds}>
                    <span>Not useful</span>
                    <span>Very useful</span>
                  </div>
                </fieldset>

                {feedback.reasons.length > 0 && (
                  <fieldset className={styles.reasonGroup}>
                    <legend className={styles.legend}>
                      What shaped that? <span className={styles.optional}>Optional</span>
                    </legend>
                    <div className={styles.chips}>
                      {feedback.reasons.map((reason) => (
                        <button
                          key={reason.value}
                          type="button"
                          aria-pressed={selected.includes(reason.value)}
                          className={`${styles.chip} ${selected.includes(reason.value) ? styles.chipOn : ''}`}
                          onClick={() => toggleReason(reason.value)}
                        >
                          {reason.label}
                        </button>
                      ))}
                    </div>
                  </fieldset>
                )}

                <label className={styles.commentLabel} htmlFor="fb-comment">
                  Anything else? <span className={styles.optional}>Optional</span>
                </label>
                <textarea
                  id="fb-comment"
                  className={styles.comment}
                  rows={4}
                  maxLength={2000}
                  value={comment}
                  onChange={(event) => setComment(event.target.value)}
                  placeholder="What worked, what did not, what you expected instead."
                />

                {feedback.error && <p className={styles.error}>{feedback.error}</p>}

                <div className={styles.actions}>
                  <button className={styles.textButton} type="button" onClick={close}>
                    Cancel
                  </button>
                  <button
                    className="primary-action"
                    type="button"
                    onClick={send}
                    disabled={rating === null || feedback.submitting}
                  >
                    {feedback.submitting ? 'Sending…' : 'Submit feedback'}
                  </button>
                </div>
                {rating === null && (
                  <p className={styles.hint}>Choose a rating to submit.</p>
                )}
              </>
            )}
          </div>
        </div>
      )}
    </>
  );
}
