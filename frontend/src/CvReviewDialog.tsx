import type { CvReview } from '@features/career-guidance';

import styles from './App.module.css';

const SEVERITY_RANK: Record<string, number> = { critical: 0, important: 1, minor: 2 };

/**
 * Critical findings only.
 *
 * The full review carries important and minor items too, but a list of a dozen
 * things to fix is not actionable. What gets a resume rejected at screening is
 * the useful subset, so that is what is shown.
 */
export function CvReviewDialog({ review, onClose }: { review: CvReview; onClose: () => void }) {
  const critical = review.findings.filter((f) => f.severity === 'critical');

  // The ATS score box gets its own short list of the biggest issues — ranked
  // across all severities, not just critical, so it still says something
  // useful on a "nothing major found" result where the list below is empty.
  const topMistakes = [...review.findings]
    .sort((a, b) => SEVERITY_RANK[a.severity] - SEVERITY_RANK[b.severity])
    .slice(0, 3)
    .map((f) => f.issue);

  return (
    <div className={styles.overlay} role="dialog" aria-modal="true" aria-labelledby="cv-title">
      <div className={styles.dialogWide}>
        <header className={styles.cvHead}>
          <p className="eyebrow">Major mistakes in your CV</p>
          <h2 id="cv-title">{critical.length > 0
            ? `${critical.length} thing${critical.length === 1 ? '' : 's'} to fix first`
            : 'Nothing major found'}</h2>
          <p className={styles.cvOverall}>{review.overall}</p>

          <div className={styles.atsScore}>
            <div className={styles.atsScoreValue}>
              {review.ats_score}
              <small>/100</small>
            </div>
            <div className={styles.atsScoreBody}>
              <h3>ATS score</h3>
              <p>
                {topMistakes.length > 0
                  ? topMistakes.join(' ')
                  : 'No specific issues identified in your parsed profile.'}
              </p>
            </div>
          </div>
        </header>

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
