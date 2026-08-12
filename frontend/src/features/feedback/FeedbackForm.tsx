import type { FeedbackReason } from './feedbackApi';
import styles from './FeedbackWidget.module.css';

const SCALE = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10];

type FeedbackFormProps = {
  rating: number | null;
  onRate: (score: number) => void;
  reasons: FeedbackReason[];
  selected: string[];
  onToggleReason: (value: string) => void;
  comment: string;
  onComment: (value: string) => void;
  error: string | null;
  submitting: boolean;
  onSubmit: () => void;
  onCancel: () => void;
};

/** The dialog body before submission. Presentational: all state lives above. */
export function FeedbackForm({
  rating,
  onRate,
  reasons,
  selected,
  onToggleReason,
  comment,
  onComment,
  error,
  submitting,
  onSubmit,
  onCancel,
}: FeedbackFormProps) {
  return (
    <>
      <p className="eyebrow">Your feedback</p>
      <h2 id="fb-title">How useful was this?</h2>

      <RatingScale rating={rating} onRate={onRate} />

      {reasons.length > 0 && (
        <ReasonChips
          reasons={reasons}
          selected={selected}
          onToggleReason={onToggleReason}
        />
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
        onChange={(event) => onComment(event.target.value)}
        placeholder="What worked, what did not, what you expected instead."
      />

      {error && <p className={styles.error}>{error}</p>}

      <div className={styles.actions}>
        <button className={styles.textButton} type="button" onClick={onCancel}>
          Cancel
        </button>
        <button
          className="primary-action"
          type="button"
          onClick={onSubmit}
          disabled={rating === null || submitting}
        >
          {submitting ? 'Sending…' : 'Submit feedback'}
        </button>
      </div>
      {rating === null && <p className={styles.hint}>Choose a rating to submit.</p>}
    </>
  );
}

function RatingScale({
  rating,
  onRate,
}: Pick<FeedbackFormProps, 'rating' | 'onRate'>) {
  return (
    <fieldset className={styles.scaleGroup}>
      <legend className={styles.legend}>Rating out of 10</legend>
      <div className={styles.scale}>
        {SCALE.map((score) => (
          <button
            key={score}
            type="button"
            aria-pressed={rating === score}
            className={`${styles.scoreBtn} ${rating === score ? styles.scoreOn : ''}`}
            onClick={() => onRate(score)}
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
  );
}

function ReasonChips({
  reasons,
  selected,
  onToggleReason,
}: Pick<FeedbackFormProps, 'reasons' | 'selected' | 'onToggleReason'>) {
  return (
    <fieldset className={styles.reasonGroup}>
      <legend className={styles.legend}>
        What shaped that? <span className={styles.optional}>Optional</span>
      </legend>
      <div className={styles.chips}>
        {reasons.map((reason) => (
          <button
            key={reason.value}
            type="button"
            aria-pressed={selected.includes(reason.value)}
            className={`${styles.chip} ${selected.includes(reason.value) ? styles.chipOn : ''}`}
            onClick={() => onToggleReason(reason.value)}
          >
            {reason.label}
          </button>
        ))}
      </div>
    </fieldset>
  );
}
