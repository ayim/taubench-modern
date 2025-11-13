import { sql, type RawBuilder } from 'kysely';

export const omitProperties = <
  Item extends Record<string, unknown>,
  Keys extends Array<keyof Item>,
  KeysUnion extends Keys[number],
  Output extends Omit<Item, KeysUnion>,
>(
  obj: Item,
  properties: Keys,
): Output => {
  return Object.keys(obj).reduce((current, key) => {
    if (properties.includes(key)) return current;

    return {
      ...current,
      [key]: obj[key],
    };
  }, {} as Output);
};

export const pickProperties = <
  Item extends Record<string, unknown>,
  Keys extends Array<keyof Item>,
  KeysUnion extends Keys[number],
  Output extends Pick<Item, KeysUnion>,
>(
  obj: Item,
  properties: Keys,
): Output => {
  return Object.keys(obj).reduce((current, key) => {
    if (!properties.includes(key)) return current;

    return {
      ...current,
      [key]: obj[key],
    };
  }, {} as Output);
};

export const sqlNow = (): RawBuilder<string> => {
  return sql<string>`now()`;
};
