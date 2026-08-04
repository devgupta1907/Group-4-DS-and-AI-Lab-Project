import { Button } from '@shared/ui';
import { formatBytes } from '@shared/utils/format';

import styles from './SelectedFileChip.module.css';

type SelectedFileChipProps = {
  file: File;
  onClear?: () => void;
};

export function SelectedFileChip({ file, onClear }: SelectedFileChipProps) {
  return (
    <div className={styles.chip}>
      <span className={styles.icon} aria-hidden="true">
        📄
      </span>
      <span className={styles.name} title={file.name}>
        {file.name}
      </span>
      <span className={styles.size}>{formatBytes(file.size)}</span>
      {onClear && (
        <Button variant="ghost" size="sm" onClick={onClear} aria-label="Remove file">
          ✕
        </Button>
      )}
    </div>
  );
}
