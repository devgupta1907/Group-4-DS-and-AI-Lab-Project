import { Alert } from '@shared/ui';

import { REVIEW_LABELS } from '../constants';

type NeedsReviewNoticeProps = {
  fields: string[];
  isValid: boolean;
};

/**
 * Explains what the parser could not find.
 *
 * Deliberately framed as information rather than error: a fresher with no
 * experience section is a correct parse, not a failed one.
 */
export function NeedsReviewNotice({ fields, isValid }: NeedsReviewNoticeProps) {
  if (!isValid) {
    return (
      <Alert tone="warning" title="This profile is partial">
        The extracted data did not fully match the expected schema, so some fields may be
        missing. The profile was saved anyway rather than discarded.
      </Alert>
    );
  }

  if (fields.length === 0) return null;

  const labels = fields.map((field) => REVIEW_LABELS[field] ?? field);

  return (
    <Alert tone="info" title={`Not found on this resume: ${labels.join(', ')}`}>
      These sections were absent from the document. Nothing was invented to fill them.
    </Alert>
  );
}
