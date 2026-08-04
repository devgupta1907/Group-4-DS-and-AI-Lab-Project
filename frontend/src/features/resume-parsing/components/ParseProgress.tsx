import { ProgressStepper } from '@shared/ui';

import { STAGE_STEPS } from '../constants';
import { useParseProgress } from '../hooks/useParseProgress';
import type { UploadStatus } from '../hooks/useResumeUpload';
import type { ParseStage } from '../types/parsedProfile';

type ParseProgressProps = {
  status: UploadStatus;
  stage: ParseStage | null;
  detail: string | null;
  completedStages: ParseStage[];
};

export function ParseProgress({
  status,
  stage,
  detail,
  completedStages,
}: ParseProgressProps) {
  const stateOf = useParseProgress({ status, stage, completedStages });

  return (
    <div aria-live="polite" aria-busy={status === 'parsing'}>
      <ProgressStepper steps={STAGE_STEPS} stateOf={stateOf} detail={detail ?? undefined} />
    </div>
  );
}
