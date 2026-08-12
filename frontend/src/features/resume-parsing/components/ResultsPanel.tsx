import { Card, EmptyState } from '@shared/ui';

import type { ResumeUpload } from '../hooks/useResumeUpload';

import { ProfileView } from './ProfileView';
import styles from './ResultsPanel.module.css';
import { ResumeScanPreview } from './ResumeScanPreview';

type ResultsPanelProps = {
  upload: ResumeUpload;
};

/**
 * The right-hand column. Holds one of three states — nothing yet, working, or
 * a profile — so the page component does not have to branch on status itself.
 */
export function ResultsPanel({ upload }: ResultsPanelProps) {
  if (upload.record) {
    return (
      <Card title="Extracted profile" description={upload.record.filename} flush>
        <ProfileView record={upload.record} />
      </Card>
    );
  }

  if (upload.status === 'parsing') {
    return (
      <Card title="Extracted profile" flush>
        {/* Parsing runs long enough that a placeholder reads as a stall.
            Showing the user's own document with a scan line passing over it
            gives the wait a subject — and it is honest, because a rendered
            page image really is what gets sent to the model. */}
        <div className={styles.scanning}>
          {upload.file && <ResumeScanPreview file={upload.file} />}
          <div className={styles.scanningText}>
            <p className={styles.scanningTitle}>Scanning the resume</p>
            <p className={styles.scanningBody}>
              Fields appear here as soon as the model finishes the document.
            </p>
          </div>
        </div>
      </Card>
    );
  }

  return (
    <Card title="Extracted profile" flush>
      <EmptyState
        icon={<span className={styles.icon}>◴</span>}
        title="No resume parsed yet"
        description="Upload a PDF, DOCX or image on the left. The extracted profile will appear here, section by section."
      />
    </Card>
  );
}
