import { request } from '@shared/api/httpClient';

import type { CareerReport, SearchPreferences } from './types';

/**
 * Runs career recommendation, live job discovery and report generation.
 *
 * Slow by nature — job discovery searches and crawls real postings — so the
 * caller is expected to show progress for the duration rather than block.
 */
export function generateReport(
  profileId: string,
  preferences: SearchPreferences,
): Promise<CareerReport> {
  return request('/career-reports', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ profile_id: profileId, ...preferences }),
  });
}

export type CvFinding = {
  area: string;
  severity: 'critical' | 'important' | 'minor';
  issue: string;
  evidence: string;
  fix: string;
};

export type CvReview = {
  overall: string;
  strengths: string[];
  findings: CvFinding[];
  missing_sections: string[];
  score: number;
  score_reason: string;
  status: string;
};

/** Critique of the stored parsed profile. Reads nothing, writes nothing. */
export function reviewCv(profileId: string): Promise<CvReview> {
  return request('/cv-review', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ profile_id: profileId }),
  });
}
