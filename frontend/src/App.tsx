import { useCallback, useMemo, useState } from 'react';

import {
  CareerReportView,
  PreferencesPanel,
  type SearchPreferences,
  useCareerGuidance,
} from '@features/career-guidance';
import {
  ProfileView,
  ResultsPanel,
  ResumeUploadPanel,
  type ProfileRecord,
  useFileValidation,
  useResumeUpload,
} from '@features/resume-parsing';

import styles from './App.module.css';

const INITIAL_PREFERENCES: SearchPreferences = {
  target_location: null,
  remote_only: false,
  min_salary_lpa: null,
};

export function App() {
  const upload = useResumeUpload();
  const validate = useFileValidation();
  const guidance = useCareerGuidance();
  const [rejection, setRejection] = useState<string | null>(null);
  const [preferences, setPreferences] = useState(INITIAL_PREFERENCES);
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
    () => { if (upload.record) void guidance.analyse(upload.record.id, preferences); },
    [guidance, preferences, upload.record],
  );

  if (guidance.report) {
    return <ReportPage report={guidance.report} parsedResume={upload.record} />;
  }

  return (
    <main className={styles.app}>
      <TopBar step={step} />
      <section className={styles.hero}>
        <div>
          <p className="eyebrow">Career navigation, grounded in your evidence</p>
          <h1>Your resume knows where you’ve been. Let’s map what’s next.</h1>
        </div>
        <p className={styles.heroCopy}>One guided analysis turns your experience into career
          directions, skill unlocks, live opportunities, and a practical 90-day plan.</p>
      </section>

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
        <section className={styles.reviewStage}>
          <div className={styles.profileRail}>
            <p className="eyebrow">Step 01 · Profile ready</p>
            <h2>{upload.record.profile.contact.name ?? 'Your profile'}</h2>
            <p>{upload.record.profile.job_titles.join(' · ') || 'Career direction open'}</p>
            <div className="chips">
              {upload.record.profile.skills.slice(0, 10).map((skill) => (
                <span key={skill}>{skill}</span>
              ))}
            </div>
            <button className={styles.textButton} type="button" onClick={upload.reset}>
              Use another resume
            </button>
          </div>
          <PreferencesPanel
            value={preferences}
            onChange={setPreferences}
            onRun={runAnalysis}
          />
        </section>
      )}

      {step === 3 && <AnalysisStage status={guidance.status} error={guidance.error}
        onRetry={runAnalysis} />}
    </main>
  );
}

function ReportPage({
  report,
  parsedResume,
}: {
  report: NonNullable<ReturnType<typeof useCareerGuidance>['report']>;
  parsedResume: ProfileRecord | null;
}) {
  return (
    <main className={styles.reportPage}>
      <TopBar step={4} />
      {parsedResume && (
        <details className={styles.parsedResume}>
          <summary><span>Testing only</span><strong>View parsed resume data</strong></summary>
          <div><ProfileView record={parsedResume} /></div>
        </details>
      )}
      <CareerReportView report={report} />
    </main>
  );
}

function TopBar({ step }: { step: number }) {
  return (
    <header className={styles.topbar}>
      <a href="/" className={styles.brand}>VECTOR<span>/</span>CAREER</a>
      <nav aria-label="Analysis progress">
        {['Resume', 'Preferences', 'Analysis', 'Report'].map((label, index) => (
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
