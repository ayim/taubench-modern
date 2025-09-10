import { describe, expect, it } from 'vitest';
import { normalizeProviderToGroup } from '../providerUtils';

describe.each([
  ['openai', 'openai'] satisfies [unknown, string],
  ['Azure OpenAI', 'azure'] satisfies [unknown, string],
  ['azure', 'azure'] satisfies [unknown, string],
  ['bedrock', 'bedrock'] satisfies [unknown, string],
  ['Amazon Bedrock', 'bedrock'] satisfies [unknown, string],
  ['unknown', 'unknown'] satisfies [unknown, string],
  [[], 'unknown'] satisfies [unknown, string],
  [{}, 'unknown'] satisfies [unknown, string],
  [undefined, 'unknown'] satisfies [unknown, string],
  [null, 'unknown'] satisfies [unknown, string],
  [false, 'unknown'] satisfies [unknown, string],
])('normalizeProviderToGroup', (input, expected) => {
  it(`should transform ${String(input)} to ${expected}`, () => {
    expect(normalizeProviderToGroup(input)).toBe(expected);
  });
});
