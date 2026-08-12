import {
  ResultsPanel,
  ResumeUploadPanel,
  type ResumeUpload,
} from '@features/resume-parsing';

import styles from './App.module.css';

type UploadStageProps = {
  upload: ResumeUpload;
  rejection: string | null;
  onSelect: (file: File) => void;
};

/** Step 01. Splits to show live parse results once something is in flight. */
export function UploadStage({ upload, rejection, onSelect }: UploadStageProps) {
  const stageIsBusy = upload.status !== 'idle' || Boolean(upload.file);

  return (
    <section className={styles.stage}>
      <p className={styles.slogan}>
        Your resume knows where you&rsquo;ve been &mdash; let&rsquo;s map what&rsquo;s next.
      </p>

      <div className={stageIsBusy ? styles.stageSplit : styles.stageSolo}>
        <div className={styles.uploadWrap}>
          <ResumeUploadPanel
            upload={upload}
            rejection={rejection}
            onSelect={onSelect}
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
  );
}
