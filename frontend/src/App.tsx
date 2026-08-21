import { useCallback, useMemo, useState } from 'react';

import {
  CareerReportView,
  reviewCv,
  useCareerGuidance,
  type CvReview,
} from '@features/career-guidance';
import { FeedbackWidget } from '@features/feedback';
import {
  useFileValidation,
  useResumeUpload,
} from '@features/resume-parsing';

import styles from './App.module.css';
import { CvReviewDialog } from './CvReviewDialog';
import { ReviewStage } from './ReviewStage';
import { UploadStage } from './UploadStage';

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

  const closeCvReview = useCallback(() => setCvReview(null), []);

  if (guidance.report) {
    return <ReportPage report={guidance.report} />;
  }

  return (
    <main className={styles.app}>
      <TopBar step={step} />

      {step === 1 && (
        <UploadStage upload={upload} rejection={rejection} onSelect={handleSelect} />
      )}

      {step === 2 && upload.record && (
        <ReviewStage
          record={upload.record}
          cvLoading={cvLoading}
          cvError={cvError}
          onRunCvReview={runCvReview}
          onRunReport={runReport}
          onReset={upload.reset}
          onProfileSaved={upload.setRecord}
        />
      )}

      {step === 3 && (
        <AnalysisStage error={guidance.error} onRetry={runReport} />
      )}

      {cvReview && <CvReviewDialog review={cvReview} onClose={closeCvReview} />}

      {/* Rendered once, outside the step branches, so the same button is
          available at every stage — including to someone who abandons the
          flow before a report, whose feedback is the most worth having. */}
      <FeedbackWidget profileId={upload.record?.id ?? null} />
    </main>
  );
}

function ReportPage({ report }: {
  report: NonNullable<ReturnType<typeof useCareerGuidance>['report']>;
}) {
  return (
    <main className={styles.reportPage}>
      <TopBar step={4} />
      <CareerReportView report={report} />
      <FeedbackWidget profileId={null} />
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
