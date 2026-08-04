/**
 * The only file that knows this feature's endpoint paths.
 *
 * Components never import it (eslint blocks that) — hooks do, and components
 * consume the hooks.
 */
import { postFileForStream, request } from '@shared/api/httpClient';
import { readSseFrames } from '@shared/api/sseClient';

import type { ParseEvent, ProfileRecord, ProfileSummary } from '../types/parsedProfile';

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

export function fetchProfiles(): Promise<ProfileSummary[]> {
  return request<ProfileSummary[]>(`${BASE}/profiles`);
}

export function deleteProfile(profileId: string): Promise<void> {
  return request<void>(`${BASE}/profiles/${profileId}`, { method: 'DELETE' });
}
