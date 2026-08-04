import { Card, EmptyState } from '@shared/ui';

import type { ResumeUpload } from '../hooks/useResumeUpload';

import { ProfileView } from './ProfileView';
import styles from './ResultsPanel.module.css';

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
        <div className={styles.working}>
          <EmptyState
            title="Reading the resume"
            description="Fields appear here as soon as the model finishes the document."
          />
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
