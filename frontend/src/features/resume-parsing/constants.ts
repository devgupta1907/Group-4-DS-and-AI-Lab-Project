import type { Step } from '@shared/ui';

import type { ParseStage } from './types/parsedProfile';

/** Mirrors the server's limits so the UI can reject a file before uploading it. */
export const MAX_UPLOAD_BYTES = 10 * 1024 * 1024;

export const ACCEPTED_TYPES = [
  'application/pdf',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'image/png',
  'image/jpeg',
  'image/webp',
] as const;

export const ACCEPT_ATTRIBUTE = '.pdf,.docx,.png,.jpg,.jpeg,.webp';

export const UPLOAD_HINT = 'PDF, DOCX, PNG or JPEG · up to 10 MB';

/**
 * The stages shown in the stepper.
 *
 * `received` and `persisting` are real server stages but are not shown: they
 * are too brief to register, and a step that flashes past reads as noise.
 */
export const VISIBLE_STAGES: readonly ParseStage[] = [
  'reading',
  'extracting',
  'refining',
  'ready',
];

export const STAGE_STEPS: readonly Step[] = [
  { id: 'reading', label: 'Reading document' },
  { id: 'extracting', label: 'Extracting fields' },
  { id: 'refining', label: 'Refining' },
  { id: 'ready', label: 'Profile ready' },
];

/** Human labels for the `needs_review` keys the server returns. */
export const REVIEW_LABELS: Record<string, string> = {
  'contact.name': 'Name',
  'contact.location': 'Location',
  skills: 'Skills',
  education: 'Education',
  experience: 'Experience',
};
