import { request } from '@shared/api/httpClient';

import type { CareerReport, SearchPreferences } from './types';

export function generateReport(
  profileId: string,
  preferences: SearchPreferences,
): Promise<CareerReport> {
  return request('/career-reports', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      profile_id: profileId,
      ...preferences,
    }),
  });
}
