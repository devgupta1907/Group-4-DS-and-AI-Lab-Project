import { Alert, Button, Card, FileDropzone } from '@shared/ui';

import { ACCEPT_ATTRIBUTE, UPLOAD_HINT } from '../constants';
import type { ResumeUpload } from '../hooks/useResumeUpload';

import { ParseProgress } from './ParseProgress';
import styles from './ResumeUploadPanel.module.css';
import { SelectedFileChip } from './SelectedFileChip';


type ResumeUploadPanelProps = {
  upload: ResumeUpload;
  /** Client-side rejection, before anything is sent. */
  rejection: string | null;
  onSelect: (file: File) => void;
  /** Switches to filling in the profile by hand instead of uploading a
      file. Omit to hide the option entirely. */
  onManualEntry?: () => void;
};

export function ResumeUploadPanel({
  upload,
  rejection,
  onSelect,
  onManualEntry,
}: ResumeUploadPanelProps) {
  const isParsing = upload.status === 'parsing';
  const isIdle = upload.status === 'idle';

  return (
    <Card
      title="Upload your resume"
      description="Read once, turned into a structured profile. Nothing is stored until parsing succeeds."
    >
      <div className={styles.panel}>
        {isIdle && !upload.file && (
          <>
            {/* Above the dropzone, not below it. Uploading a resume means
                handing over a document full of personal history, so what
                happens to it should be readable before the choice is made
                rather than discovered afterwards. */}
            <div className={styles.privacy}>
              <span className={styles.privacyIcon} aria-hidden="true">🔒</span>
              <div>
                <p className={styles.privacyTitle}>Your personal data is safe here</p>
                <ul className={styles.privacyList}>
                  <li>Email addresses and phone numbers are never extracted or stored.</li>
                  <li>The file itself is never kept — only the structured profile is saved.</li>
                  <li>Stored fields are encrypted, and you can delete your profile at any time.</li>
                </ul>
              </div>
            </div>

            <FileDropzone
              accept={ACCEPT_ATTRIBUTE}
              hint={UPLOAD_HINT}
              disabled={isParsing}
              onSelect={onSelect}
            />

            {onManualEntry && (
              <button type="button" className={styles.manualLink} onClick={onManualEntry}>
                Prefer not to upload a file? Enter your details manually instead.
              </button>
            )}
          </>
        )}

        {upload.file && (
          <SelectedFileChip
            file={upload.file}
            onClear={isParsing ? undefined : upload.reset}
          />
        )}

        {rejection && <Alert tone="danger" title={rejection} />}

        {upload.status === 'failed' && upload.error && (
          <Alert tone="danger" title={upload.error.message}>
            <span className={styles.code}>{upload.error.code}</span>
          </Alert>
        )}

        {!isIdle && (
          <div className={styles.progress}>
            <ParseProgress
              status={upload.status}
              stage={upload.stage}
              detail={upload.detail}
              completedStages={upload.completedStages}
            />
          </div>
        )}

        <div className={styles.actions}>
          {isParsing && (
            <Button variant="secondary" onClick={upload.cancel}>
              Cancel
            </Button>
          )}
          {!isParsing && !isIdle && (
            <Button variant="secondary" onClick={upload.reset}>
              Parse another resume
            </Button>
          )}
        </div>

        <p className={styles.disclosure}>
          The rendered page is sent to the model provider to be read. Email addresses and
          phone numbers are excluded from the extracted profile and are never stored.
        </p>
      </div>
    </Card>
  );
}
