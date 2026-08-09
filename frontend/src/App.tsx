import { useCallback, useMemo, useState } from 'react';

import {
  CareerReportView,
  reviewCv,
  useCareerGuidance,
  type CvReview,
} from '@features/career-guidance';
import {
  ProfileView,
  ResultsPanel,
  ResumeUploadPanel,
  useFileValidation,
  useResumeUpload,
} from '@features/resume-parsing';

import styles from './App.module.css';

const DEFAULT_PREFERENCES = {
  target_location: null,
  remote_only: false,
  min_salary_lpa: null,
};

export function App() {
  const upload = useResumeUpload();
  const validate = useFileValidation();
  const guidance = useCareerGuidance();
  const [rejection, setRejection] = useState<string | null>(null);
  const [cvReview, setCvReview] = useState<CvReview | null>(null);
  const [cvLoading, setCvLoading] = useState(false);
  const [cvError, setCvError] = useState<string | null>(null);

  const step = useMemo(() => {
    if (guidance.report) return 4;
    if (guidance.status === 'recommending' || guidance.status === 'reporting') return 3;
    if (upload.record) return 2;
    return 1;
  }, [guidance.report, guidance.status, upload.record]);

  const handleSelect = useCallback(
    (file: File) => {
      const problem = validate(file);
      setRejection(problem?.message ?? null);
      if (!problem) {
        guidance.reset();
        setCvReview(null);
        setCvError(null);
        upload.upload(file);
      }
    },
    [guidance, upload, validate],
  );

  // Straight to the report. The intermediate careers dialog was removed: once
  // the confidence bands and per-role reasoning came out of it, it showed five
  // bare occupation titles, which is not enough for the user to decide
  // anything on. The occupations still appear in the report, where they carry
  // their evidence.
  const runReport = useCallback(() => {
    if (upload.record) void guidance.buildReport(upload.record.id, DEFAULT_PREFERENCES);
  }, [guidance, upload.record]);

  const runCvReview = useCallback(async () => {
    if (!upload.record) return;
    setCvLoading(true);
    setCvError(null);
    try {
      setCvReview(await reviewCv(upload.record.id));
    } catch {
      // Surfaced rather than swallowed: a button that silently does nothing
      // reads as a broken page.
      setCvError('The review could not be generated. Please try again.');
    } finally {
      setCvLoading(false);
    }
  }, [upload.record]);

  if (guidance.report) {
    return <ReportPage report={guidance.report} />;
  }

  const stageIsBusy = upload.status !== 'idle' || Boolean(upload.file);

  return (
    <main className={styles.app}>
      <TopBar step={step} />

      {step === 1 && (
        <section className={styles.stage}>
          <p className={styles.slogan}>
            Your resume knows where you&rsquo;ve been &mdash; let&rsquo;s map what&rsquo;s next.
          </p>

          <div className={stageIsBusy ? styles.stageSplit : styles.stageSolo}>
            <div className={styles.uploadWrap}>
              <ResumeUploadPanel
                upload={upload}
                rejection={rejection}
                onSelect={handleSelect}
              />
            </div>
            {stageIsBusy && (
              <div className={styles.resultsWrap}>
                <ResultsPanel upload={upload} />
              </div>
            )}
          </div>

          {!stageIsBusy && (
            <ul className={styles.promise}>
              <li><b>Career directions</b><span>Matched against relevant occupations.</span></li>
              <li><b>Live opportunities</b><span>Real postings, ranked and explained.</span></li>
              <li><b>A 90-day plan</b><span>Concrete weekly steps, not generic advice.</span></li>
            </ul>
          )}
        </section>
      )}

      {step === 2 && upload.record && (
        <section className={styles.reviewProfile}>
          <header>
            <div>
              <p className="eyebrow">Step 02 · Review parsed resume</p>
              <h1>Check what we extracted before analysis.</h1>
              <p>Career guidance will use exactly this profile.</p>
            </div>
            {/* Both actions live together at the top: one critiques the CV,
                one moves forward. Pairing them makes the review a visible
                option rather than something buried below the fold. */}
            <div className={styles.headerActions}>
              <button
                className={styles.secondaryAction}
                type="button"
                onClick={runCvReview}
                disabled={cvLoading}
              >
                {cvLoading ? 'Checking…' : 'Major Mistakes in CV'}
              </button>
              <button className="primary-action" type="button" onClick={runReport}>
                Get Analysis <span aria-hidden="true">→</span>
              </button>
            </div>
          </header>

          {cvError && <div className={styles.error}>{cvError}</div>}

          <ProfileView record={upload.record} />

          <footer>
            <button className={styles.textButton} type="button" onClick={upload.reset}>
              Use another resume
            </button>
            <button className="primary-action" type="button" onClick={runReport}>
              Get Analysis <span aria-hidden="true">→</span>
            </button>
          </footer>
        </section>
      )}

      {step === 3 && (
        <AnalysisStage error={guidance.error} onRetry={runReport} />
      )}

      {cvReview && (
        <CvReviewDialog review={cvReview} onClose={() => setCvReview(null)} />
      )}
    </main>
  );
}

/**
 * Critical findings only.
 *
 * The full review carries important and minor items too, but a list of a dozen
 * things to fix is not actionable. What gets a resume rejected at screening is
 * the useful subset, so that is what is shown.
 */
function CvReviewDialog({ review, onClose }: { review: CvReview; onClose: () => void }) {
  const critical = review.findings.filter((f) => f.severity === 'critical');

  return (
    <div className={styles.overlay} role="dialog" aria-modal="true" aria-labelledby="cv-title">
      <div className={styles.dialogWide}>
        {/* No score. A bare number out of 100 carried no scale, no basis and
            no comparison, so it invited a question the feature could not
            answer. The findings are the substance. */}
        <header className={styles.cvHead}>
          <p className="eyebrow">Major mistakes in your CV</p>
          <h2 id="cv-title">{critical.length > 0
            ? `${critical.length} thing${critical.length === 1 ? '' : 's'} to fix first`
            : 'Nothing major found'}</h2>
          <p className={styles.cvOverall}>{review.overall}</p>
        </header>

        {critical.length === 0 && (
          <p className={styles.dialogNote}>
            Nothing here would get your resume rejected at screening. Smaller
            improvements appear in the full report.
          </p>
        )}

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

function ReportPage({ report }: {
  report: NonNullable<ReturnType<typeof useCareerGuidance>['report']>;
}) {
  return (
    <main className={styles.reportPage}>
      <TopBar step={4} />
      <CareerReportView report={report} />
    </main>
  );
}

function TopBar({ step }: { step: number }) {
  return (
    <header className={styles.topbar}>
      <a href="/" className={styles.brand}>
        <img src="/logo.png" alt="" aria-hidden="true" />
        <span>Discover<b>MyRole</b></span>
      </a>
      <nav aria-label="Analysis progress">
        {['Resume', 'Review', 'Analysis', 'Report'].map((label, index) => (
          <span className={index + 1 <= step ? styles.activeStep : ''} key={label}>
            {index + 1} {label}
          </span>
        ))}
      </nav>
    </header>
  );
}

/**
 * One message for both phases, and no duration.
 *
 * Naming the stage told the user about our pipeline rather than about their
 * request, and quoting a time we cannot hold — job search latency depends on
 * external engines — turns a slow run into a broken promise.
 */
function AnalysisStage({
  error,
  onRetry,
}: {
  error: string | null;
  onRetry: () => void;
}) {
  return (
    <section className={styles.analysis}>
      <div className={styles.orbit} aria-hidden="true"><i /><i /><i /></div>
      <p className="eyebrow">Step 03 · Analysis</p>
      <h2>Generating your report…</h2>
      <p>Please keep this page open.</p>
      {error && <div className={styles.error}>{error}<button onClick={onRetry}>Try again</button></div>}
    </section>
  );
}
