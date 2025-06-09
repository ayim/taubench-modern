import fs from 'fs';
import path from 'path';

import { streamEventSource } from './stream';

const loadSSEFileAsChunks = (filePath: string): string[] => {
  const content = fs.readFileSync(filePath, 'utf-8');
  return content.split(/\n\n+/);
};

const createMockReadableStream = (chunks: string[]) => {
  const encoder = new TextEncoder();
  let i = 0;
  return {
    getReader() {
      return {
        read: jest.fn().mockImplementation(() => {
          if (i < chunks.length) {
            const value = encoder.encode(chunks[i++] + '\n\n');
            return Promise.resolve({ value, done: false });
          } else {
            return Promise.resolve({ done: true });
          }
        }),
      };
    },
  };
};

describe('streamEventSource', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('should call onEvent for each SSE chunk parsed', async () => {
    const fixturePath = path.join(process.cwd(), '__fixtures__', 'mockSSE.txt');
    const sseChunks = loadSSEFileAsChunks(fixturePath);

    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      body: createMockReadableStream(sseChunks),
    });
    const mockOnEvent = jest.fn();
    const mockOnDone = jest.fn();
    const mockOnError = jest.fn();

    const stream = streamEventSource({
      method: 'POST',
      url: 'https://example.com/sse',
      body: '{}',
    });

    await stream.start({
      onEvent: mockOnEvent,
      onDone: mockOnDone,
      onError: mockOnError,
    });

    for (const call of mockOnEvent.mock.calls) {
      expect(call[0]).toEqual(
        expect.objectContaining({
          event: expect.anything(),
          data: expect.anything(),
        })
      );
    }
  });
});
