import type { CvReview } from '@features/career-guidance';

import styles from './App.module.css';

export function CvReviewDialog({ review, onClose }: { review: CvReview; onClose: () => void }) {
  const critical = review.findings.filter((f) => f.severity === 'critical');

  // Restored per request, but deliberately still excludes critical findings
  // from this summary — those get their own full card below (issue +
  // evidence + fix). Including them here again is what caused the same
  // sentence to appear twice on screen; excluding them keeps the summary
  // useful without reintroducing that.
  const nonCriticalMistakes = [...review.findings]
    .filter((f) => f.severity !== 'critical')
    .slice(0, 3)
    .map((f) => f.issue);

  const atsSummaryText =
    nonCriticalMistakes.length > 0
      ? nonCriticalMistakes.join(' ')
      : critical.length > 0
        ? `See the ${critical.length} critical issue${critical.length === 1 ? '' : 's'} below for details.`
        : 'No specific issues identified in your parsed profile.';

  const fixCountLabel =
    critical.length > 0
      ? `${critical.length} thing${critical.length === 1 ? '' : 's'} to fix first`
      : 'Nothing major found';

  return (
    <div className={styles.overlay} role="dialog" aria-modal="true" aria-labelledby="cv-title">
      <div className={styles.dialogWide}>
        <header className={styles.cvHead}>
          <h2 id="cv-title">Major mistakes &amp; ATS score</h2>

          <div className={styles.atsScore}>
            <div className={styles.atsScoreValue}>
              {review.ats_score}
              <small>/100</small>
            </div>
            <div className={styles.atsScoreBody}>
              <h3>ATS score</h3>
              <p>{atsSummaryText}</p>
            </div>
          </div>
        </header>

        {/* Outside .cvHead deliberately — .cvHead has the border-bottom that
            visually closes the score section. Sitting after that border,
            sized as a real heading rather than a caption, is what makes
            this read as "the mistakes section starts here" instead of
            blending into the score box above it. */}
        <p className={styles.fixCountLabel}>{fixCountLabel}</p>

        <ul className={styles.findings}>
          {critical.map((finding, index) => (
            <li key={`${finding.area}-${index}`}>
              <span className={styles.findingArea}>{finding.area}</span>
              <p className={styles.findingIssue}>{finding.issue}</p>
              {finding.evidence && (
                <p className={styles.findingEvidence}>&ldquo;{finding.evidence}&rdquo;</p>
              )}
              <p className={styles.findingFix}><b>Fix:</b> {finding.fix}</p>
            </li>
          ))}
        </ul>

        <p className={styles.dialogNote}>
          This is a tentative ATS score computed from your parsed resume data. Actual ATS
          scores vary from company to company depending on their specific system.
        </p>

        <div className={styles.dialogActions}>
          <span />
          <button className="primary-action" type="button" onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
