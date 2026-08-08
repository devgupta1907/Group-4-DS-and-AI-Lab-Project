import { useCallback, useMemo, useState } from 'react';

import {
  CareerReportView,
  useCareerGuidance,
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
  const step = useMemo(
    () => guidance.report ? 4 : guidance.status !== 'idle' ? 3 : upload.record ? 2 : 1,
    [guidance.report, guidance.status, upload.record],
  );
  const handleSelect = useCallback(
    (file: File) => {
      const problem = validate(file);
      setRejection(problem?.message ?? null);
      if (!problem) {
        guidance.reset();
        upload.upload(file);
      }
    },
    [guidance, upload, validate],
  );

  const runAnalysis = useCallback(
    () => { if (upload.record) void guidance.analyse(upload.record.id, DEFAULT_PREFERENCES); },
    [guidance, upload.record],
  );

  if (guidance.report) {
    return <ReportPage report={guidance.report} />;
  }

  return (
    <main className={styles.app}>
      <TopBar step={step} />
      {step === 1 && <section className={styles.hero}>
        <div>
          <p className="eyebrow">Career navigation, grounded in your evidence</p>
          <h1>Your resume knows where you’ve been. Let’s map what’s next.</h1>
        </div>
        <p className={styles.heroCopy}>One guided analysis turns your experience into career
          directions, skill unlocks, live opportunities, and a practical 90-day plan.</p>
      </section>}

      {step === 1 && (
        <section className={styles.resumeStage}>
          <ResumeUploadPanel
            upload={upload}
            rejection={rejection}
            onSelect={handleSelect}
          />
          <ResultsPanel upload={upload} />
        </section>
      )}

      {step === 2 && upload.record && (
        <section className={styles.reviewProfile}>
          <header>
            <div><p className="eyebrow">Step 02 · Review parsed resume</p>
              <h1>Check what we extracted before analysis.</h1>
              <p>Career guidance will use exactly this profile.</p></div>
            <button className="primary-action" type="button" onClick={runAnalysis}>
              Next: generate report <span aria-hidden="true">→</span>
            </button>
          </header>
          <ProfileView record={upload.record} />
          <footer>
            <button className={styles.textButton} type="button" onClick={upload.reset}>
              Use another resume
            </button>
            <button className="primary-action" type="button" onClick={runAnalysis}>
              Next: generate report <span aria-hidden="true">→</span>
            </button>
          </footer>
        </section>
      )}

      {step === 3 && <AnalysisStage status={guidance.status} error={guidance.error}
        onRetry={runAnalysis} />}
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
    </main>
  );
}

function TopBar({ step }: { step: number }) {
  return (
    <header className={styles.topbar}>
      <a href="/" className={styles.brand}>VECTOR<span>/</span>CAREER</a>
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

function AnalysisStage({
  status,
  error,
  onRetry,
}: {
  status: string;
  error: string | null;
  onRetry: () => void;
}) {
  return (
    <section className={styles.analysis}>
      <div className={styles.orbit} aria-hidden="true"><i /><i /><i /></div>
      <p className="eyebrow">Step 03 · Intelligence in motion</p>
      <h2>{status === 'reporting' ? 'Writing your guidance report…' : 'Reading the market around you…'}</h2>
      <p>
        {status === 'reporting'
          ? 'Connecting the strongest evidence, recurring gaps, and practical next moves.'
          : 'Career matching and live job discovery are running together.'}
      </p>
      {error && <div className={styles.error}>{error}<button onClick={onRetry}>Try again</button></div>}
    </section>
  );
}
