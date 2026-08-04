/**
 * A minimal Server-Sent Events reader over a `fetch` response body.
 *
 * The browser's `EventSource` only does GET, and our upload is a multipart
 * POST, so the stream has to be parsed by hand. It is a small format: frames
 * are separated by a blank line, and each line is `field: value`.
 */

export type SseFrame = {
  /** The `event:` field. `'message'` when the server omits it, per the spec. */
  event: string;
  /** The `data:` field, with multi-line data rejoined. */
  data: string;
};

const FRAME_SEPARATOR = /\r?\n\r?\n/;

function parseFrame(block: string): SseFrame | null {
  let event = 'message';
  const data: string[] = [];

  for (const line of block.split(/\r?\n/)) {
    if (!line || line.startsWith(':')) continue; // blank or comment
    const colon = line.indexOf(':');
    const field = colon === -1 ? line : line.slice(0, colon);
    const value = colon === -1 ? '' : line.slice(colon + 1).replace(/^ /, '');
    if (field === 'event') event = value;
    else if (field === 'data') data.push(value);
  }

  return data.length > 0 || event !== 'message' ? { event, data: data.join('\n') } : null;
}

/** Yields frames as they arrive on the response body. */
export async function* readSseFrames(response: Response): AsyncGenerator<SseFrame> {
  const body = response.body;
  if (!body) return;

  const reader = body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = '';

  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += value;
      // A trailing partial frame stays in the buffer until its blank line lands.
      const blocks = buffer.split(FRAME_SEPARATOR);
      buffer = blocks.pop() ?? '';

      for (const block of blocks) {
        const frame = parseFrame(block);
        if (frame) yield frame;
      }
    }

    const trailing = parseFrame(buffer);
    if (trailing) yield trailing;
  } finally {
    reader.releaseLock();
  }
}
