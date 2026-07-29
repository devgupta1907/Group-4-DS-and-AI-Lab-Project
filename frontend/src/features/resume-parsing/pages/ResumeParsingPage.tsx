import { useCallback, useState } from 'react';

import { ResultsPanel } from '../components/ResultsPanel';
import { ResumeUploadPanel } from '../components/ResumeUploadPanel';
import { useFileValidation } from '../hooks/useFileValidation';
import { useResumeUpload } from '../hooks/useResumeUpload';

import styles from './ResumeParsingPage.module.css';

/**
 * The feature's single screen: upload on the left, extracted profile on the
 * right. All state lives in hooks; this composes and wires them.
 */
export function ResumeParsingPage() {
  const upload = useResumeUpload();
  const validate = useFileValidation();
  const [rejection, setRejection] = useState<string | null>(null);

  const handleSelect = useCallback(
    (file: File) => {
      const problem = validate(file);
      setRejection(problem?.message ?? null);
      if (!problem) upload.upload(file);
    },
    [validate, upload],
  );

  return (
    <div className={styles.page}>
      <header className={styles.masthead}>
        <p className={styles.eyebrow}>Module 1 · Resume Parsing</p>
        <h1 className={styles.title}>Turn a resume into a structured profile</h1>
        <p className={styles.lede}>
          Upload a resume in any common format. It is routed to a text or vision path,
          extracted against a fixed schema, validated, and shown back to you.
        </p>
      </header>

      <div className={styles.columns}>
        <div className={styles.left}>
          <ResumeUploadPanel
            upload={upload}
            rejection={rejection}
            onSelect={handleSelect}
          />
        </div>
        <div className={styles.right}>
          <ResultsPanel upload={upload} />
        </div>
      </div>
    </div>
  );
}
