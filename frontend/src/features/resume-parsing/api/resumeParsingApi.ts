/**
 * The only file that knows this feature's endpoint paths.
 *
 * Components never import it (eslint blocks that) — hooks do, and components
 * consume the hooks.
 */
import { postFileForStream, request } from '@shared/api/httpClient';
import { readSseFrames } from '@shared/api/sseClient';

import type { CandidateProfile, ParseEvent, ProfileRecord, ProfileSummary } from '../types/parsedProfile';

const BASE = '/resume-parsing';

/**
 * Uploads a resume and yields each parse event as the server emits it.
 *
 * The stream terminates on the server's `done` frame. Malformed frames are
 * skipped rather than thrown: one bad frame should not abandon a parse that is
 * otherwise progressing.
 */
export async function* parseResume(
  file: File,
  signal?: AbortSignal,
): AsyncGenerator<ParseEvent> {
  const response = await postFileForStream(`${BASE}/resumes`, file, signal);

  for await (const frame of readSseFrames(response)) {
    if (frame.event === 'done') return;
    try {
      yield JSON.parse(frame.data) as ParseEvent;
    } catch {
      continue;
    }
  }
}

export function fetchProfile(profileId: string): Promise<ProfileRecord> {
  return request<ProfileRecord>(`${BASE}/profiles/${profileId}`);
}

/**
 * Saves a profile typed in directly — no upload, no parsing. Sends the FULL
 * `CandidateProfile` shape `ManualProfileForm` builds and gets back a normal
 * `ProfileRecord` (route `"manual"`), the same shape a completed parse
 * returns.
 */
export function submitManualProfile(profile: CandidateProfile): Promise<ProfileRecord> {
  return request<ProfileRecord>(`${BASE}/profiles/manual`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(profile),
  });
}

/**
 * Overwrites the stored profile with candidate-edited content. Sends the
 * FULL `CandidateProfile` shape, not a partial patch — the caller edits a
 * copy of what `fetchProfile`/the upload stream returned and sends the
 * whole thing back.
 */
export function updateProfile(
  profileId: string,
  profile: CandidateProfile,
): Promise<ProfileRecord> {
  return request<ProfileRecord>(`${BASE}/profiles/${profileId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(profile),
  });
}

export function fetchProfiles(): Promise<ProfileSummary[]> {
  return request<ProfileSummary[]>(`${BASE}/profiles`);
}

export function deleteProfile(profileId: string): Promise<void> {
  return request<void>(`${BASE}/profiles/${profileId}`, { method: 'DELETE' });
}
