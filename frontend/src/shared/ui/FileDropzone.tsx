import { useCallback, useId, useState } from 'react';
import type { DragEvent } from 'react';

import styles from './FileDropzone.module.css';

type FileDropzoneProps = {
  accept: string;
  hint: string;
  disabled?: boolean;
  onSelect: (file: File) => void;
};

/**
 * Drag-and-drop plus a real `<input type="file">` behind it, so the control is
 * keyboard- and screen-reader-operable rather than mouse-only.
 */
export function FileDropzone({ accept, hint, disabled, onSelect }: FileDropzoneProps) {
  const inputId = useId();
  const [isDragging, setIsDragging] = useState(false);

  const handleDrop = useCallback(
    (event: DragEvent<HTMLLabelElement>) => {
      event.preventDefault();
      setIsDragging(false);
      if (disabled) return;
      const file = event.dataTransfer.files[0];
      if (file) onSelect(file);
    },
    [disabled, onSelect],
  );

  const handleDragOver = (event: DragEvent<HTMLLabelElement>) => {
    event.preventDefault();
    if (!disabled) setIsDragging(true);
  };

  return (
    <label
      htmlFor={inputId}
      className={[styles.zone, isDragging && styles.dragging, disabled && styles.disabled]
        .filter(Boolean)
        .join(' ')}
      onDragOver={handleDragOver}
      onDragLeave={() => setIsDragging(false)}
      onDrop={handleDrop}
    >
      <input
        id={inputId}
        type="file"
        accept={accept}
        disabled={disabled}
        className={styles.input}
        onChange={(event) => {
          const file = event.target.files?.[0];
          if (file) onSelect(file);
          event.target.value = '';
        }}
      />
      <span className={styles.icon} aria-hidden="true">
        ⬆
      </span>
      <span className={styles.primary}>
        Drop a resume here or <span className={styles.link}>browse</span>
      </span>
      <span className={styles.hint}>{hint}</span>
    </label>
  );
}
