import { useCallback, useState } from 'react';

import { Button, Card } from '@shared/ui';

import { ManualProfileForm } from '../components/ManualProfileForm';
import { ProfileView } from '../components/ProfileView';
import { ResultsPanel } from '../components/ResultsPanel';
import { ResumeUploadPanel } from '../components/ResumeUploadPanel';
import { useFileValidation } from '../hooks/useFileValidation';
import { useResumeUpload } from '../hooks/useResumeUpload';
import type { ProfileRecord } from '../types/parsedProfile';

import styles from './ResumeParsingPage.module.css';

type EntryMode = 'upload' | 'manual-form' | 'manual-result';

/**
 * The feature's single screen: an entry method on the left, the resulting
 * profile on the right. All state lives in hooks; this composes and wires
 * them.
 *
 * Entry has two paths: upload a resume (parsed and persisted via
 * `useResumeUpload`), or fill the same fields in by hand and POST them
 * straight to `/profiles/manual` (`ManualProfileForm`, via
 * `useManualProfileSubmit`). Both paths end up with a real, persisted
 * `ProfileRecord` — the manual one just skips routing and extraction — so
 * the result is shown the same way either time: `ProfileView`, which
 * already knows how to display and edit any `ProfileRecord` regardless of
 * how it was produced.
 */
export function ResumeParsingPage() {
  const upload = useResumeUpload();
  const validate = useFileValidation();
  const [rejection, setRejection] = useState<string | null>(null);

  const [mode, setMode] = useState<EntryMode>('upload');
  const [manualRecord, setManualRecord] = useState<ProfileRecord | null>(null);

  const handleSelect = useCallback(
    (file: File) => {
      const problem = validate(file);
      setRejection(problem?.message ?? null);
      if (!problem) upload.upload(file);
    },
    [validate, upload],
  );

  const handleManualSubmit = useCallback((record: ProfileRecord) => {
    setManualRecord(record);
    setMode('manual-result');
  }, []);

  const handleBackToUpload = useCallback(() => {
    setManualRecord(null);
    setMode('upload');
  }, []);

  return (
    <div className={styles.page}>
      <header className={styles.masthead}>
        <p className={styles.eyebrow}>Module 1 · Resume Parsing</p>
        <h1 className={styles.title}>Turn a resume into a structured profile</h1>
        <p className={styles.lede}>
          Upload a resume in any common format. It is routed to a text or vision path,
          extracted against a fixed schema, validated, and shown back to you. Prefer not to
          upload a file? You can fill in the same fields by hand instead.
        </p>
      </header>

      {mode === 'upload' && (
        <div className={styles.columns}>
          <div className={styles.left}>
            <ResumeUploadPanel
              upload={upload}
              rejection={rejection}
              onSelect={handleSelect}
              onManualEntry={() => setMode('manual-form')}
            />
          </div>
          <div className={styles.right}>
            <ResultsPanel upload={upload} />
          </div>
        </div>
      )}

      {mode === 'manual-form' && (
        <ManualProfileForm onSubmit={handleManualSubmit} onCancel={handleBackToUpload} />
      )}

      {mode === 'manual-result' && manualRecord && (
        <div className={styles.manualResult}>
          <div className={styles.manualResultBar}>
            <Button variant="ghost" size="sm" onClick={handleBackToUpload}>
              <span aria-hidden="true">←</span> Parse or enter another
            </Button>
          </div>
          <Card title="Your profile" description={manualRecord.filename} flush>
            <ProfileView record={manualRecord} onSaved={setManualRecord} />
          </Card>
        </div>
      )}
    </div>
  );
}
