import { useCallback } from 'react';

import type { Step, StepState } from '@shared/ui';

import { VISIBLE_STAGES } from '../constants';
import type { ParseStage } from '../types/parsedProfile';

import type { UploadStatus } from './useResumeUpload';

type ProgressInput = {
  status: UploadStatus;
  stage: ParseStage | null;
  completedStages: readonly ParseStage[];
};

/** A stage the server already announced: it is current, finished, or failed on. */
function resolveReached(
  step: ParseStage,
  stage: ParseStage | null,
  status: UploadStatus,
): StepState {
  if (stage !== step) return 'done';
  if (status === 'failed') return 'failed';
  return status === 'parsing' ? 'active' : 'done';
}

function comesBefore(step: ParseStage, current: ParseStage): boolean {
  const stepIndex = VISIBLE_STAGES.indexOf(step);
  const currentIndex = VISIBLE_STAGES.indexOf(current);
  return stepIndex !== -1 && currentIndex !== -1 && stepIndex < currentIndex;
}

/**
 * Turns the upload's raw stage timeline into per-step visual state.
 *
 * Kept out of the component because it is a small state machine, and out of
 * `ProgressStepper` because that primitive stays feature-agnostic.
 *
 * `refining` is the interesting case: it only runs when the primary model
 * failed validation, so on a clean parse it is never announced and must stay
 * pending rather than being back-filled as complete.
 */
export function useParseProgress({ status, stage, completedStages }: ProgressInput) {
  return useCallback(
    (step: Step): StepState => {
      const stepStage = step.id as ParseStage;

      if (completedStages.includes(stepStage)) {
        return resolveReached(stepStage, stage, status);
      }
      if (status === 'succeeded') {
        return stepStage === 'refining' ? 'pending' : 'done';
      }
      if (status === 'parsing' && stage !== null && comesBefore(stepStage, stage)) {
        return 'done';
      }
      return 'pending';
    },
    [status, stage, completedStages],
  );
}
