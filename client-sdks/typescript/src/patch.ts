import { applyPatch, Operation } from 'json-joy/lib/json-patch';

export type Delta =
  | Operation
  | {
      op: 'concat_string';
      path: string;
      value: any;
    };

export function applyDelta<T extends Record<string, unknown>>(
  message: T,
  delta: Delta
): T {
  if (delta.op === 'concat_string') {
    const pathParts = delta.path.slice(1).split('/');
    const newMessage = structuredClone(message);
    let ref: any = newMessage;

    for (let i = 0; i < pathParts.length - 1; i++) {
      const part = isNaN(Number(pathParts[i]))
        ? pathParts[i]
        : Number(pathParts[i]);
      if (ref[part] === undefined) {
        ref[part] =
          typeof pathParts[i + 1] === 'string' &&
          isNaN(Number(pathParts[i + 1]))
            ? {}
            : [];
      }
      ref = ref[part];
    }

    const lastPart = isNaN(Number(pathParts.at(-1)!))
      ? pathParts.at(-1)!
      : Number(pathParts.at(-1)!);

    const existing = ref[lastPart] ?? '';
    ref[lastPart] = String(existing) + delta.value;

    return newMessage;
  } else {
    const result = applyPatch(message, [delta], {
      mutate: false,
    });

    return result.doc as T;
  }
}
