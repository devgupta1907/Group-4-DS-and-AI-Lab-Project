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
};

export function ResumeUploadPanel({
  upload,
  rejection,
  onSelect,
}: ResumeUploadPanelProps) {
  const isParsing = upload.status === 'parsing';
  const isIdle = upload.status === 'idle';

  return (
    <Card
      title="Upload a resume"
      description="Parsed into a structured profile. Nothing is stored until parsing succeeds."
    >
      <div className={styles.panel}>
        {isIdle && !upload.file && (
          <FileDropzone
            accept={ACCEPT_ATTRIBUTE}
            hint={UPLOAD_HINT}
            disabled={isParsing}
            onSelect={onSelect}
          />
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
