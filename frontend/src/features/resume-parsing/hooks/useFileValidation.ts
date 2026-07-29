import { useCallback } from 'react';

import { ACCEPTED_TYPES, MAX_UPLOAD_BYTES } from '../constants';

export type FileRejection = {
  code: 'unsupported_file_type' | 'file_too_large' | 'empty_file';
  message: string;
};

const EXTENSIONS = ['.pdf', '.docx', '.png', '.jpg', '.jpeg', '.webp'];

function hasAcceptedExtension(name: string): boolean {
  const lowered = name.toLowerCase();
  return EXTENSIONS.some((extension) => lowered.endsWith(extension));
}

/**
 * Pre-flight checks that mirror the server's.
 *
 * This is a courtesy, not a control: the server re-checks everything. Its value
 * is that an oversized file fails instantly instead of after a 10 MB upload.
 */
export function useFileValidation() {
  return useCallback((file: File): FileRejection | null => {
    if (file.size === 0) {
      return { code: 'empty_file', message: 'That file is empty.' };
    }

    // Browsers often report an empty or wrong MIME type, so the extension is
    // the more reliable signal — the same order the server uses.
    const typeIsAccepted = (ACCEPTED_TYPES as readonly string[]).includes(file.type);
    if (!hasAcceptedExtension(file.name) && !typeIsAccepted) {
      return {
        code: 'unsupported_file_type',
        message: 'Upload a PDF, DOCX, PNG or JPEG resume.',
      };
    }

    if (file.size > MAX_UPLOAD_BYTES) {
      return {
        code: 'file_too_large',
        message: 'That file is larger than the 10 MB limit.',
      };
    }

    return null;
  }, []);
}
