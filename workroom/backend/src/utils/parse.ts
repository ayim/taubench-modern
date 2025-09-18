export const caseless = <T extends Record<string, unknown>>(
  map: T,
): { [K in keyof T as Lowercase<string & K>]: T[K] } => {
  const output = {} as { [K in keyof T as Lowercase<string & K>]: T[K] };

  for (const key in map) {
    if (Object.prototype.hasOwnProperty.call(map, key)) {
      const lowercaseKey = key.toLowerCase();
      // Type assertion acknowledges we know the transformation is correct
      (output as Record<string, T[keyof T]>)[lowercaseKey] = map[key];
    }
  }

  return output;
};

/**
 * Parses `Cookie` header strings, breaking them up into their component
 *  properties. Each value is URI decoded.
 * @example
 *  parseCookies('PHPSESSID=298zf09hf012fh2; csrftoken=u32t4o3tb3gg43');
 *  // {
 *  //   PHPSESSID: '298zf09hf012fh2',
 *  //   csrftoken: 'u32t4o3tb3gg43
 *  // }
 */
export const parseCookies = (cookieHeader: string): Record<string, string> => {
  if (!cookieHeader || cookieHeader.trim().length === 0) {
    return {};
  }

  return cookieHeader.split(';').reduce(
    (output, cookie) => {
      const trimmed = cookie.trim();
      const equalIndex = trimmed.indexOf('=');

      if (equalIndex > 0) {
        const name = trimmed.substring(0, equalIndex).trim();
        const value = decodeURIComponent(trimmed.substring(equalIndex + 1).trim());

        return {
          ...output,
          [name]: value,
        };
      }

      return output;
    },
    {} as Record<string, string>,
  );
};
