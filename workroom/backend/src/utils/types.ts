export function exhaustiveUnionArray<T>() {
  return <U extends readonly T[]>(array: U & (Exclude<T, U[number]> extends never ? U : never)) => array;
}
