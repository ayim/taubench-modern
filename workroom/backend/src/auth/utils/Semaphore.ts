/**
 * Asynchronous semaphore management utility -
 * Helps prevent more than 1 asynchronous operation occuring at
 * a time for a given key.
 */
export class Semaphore<Result, Index extends string = string> {
  private collection = new Map<Index, Promise<Result>>();

  /**
   * Use the semaphore ona given key - blocks access to said key
   * for the duration of the asynchronous task
   */
  async use(key: Index, callback: () => Promise<Result>): Promise<Result> {
    const existing = this.collection.get(key);
    if (existing) return existing;

    // No existing work, run and create anew
    const work = callback();
    this.collection.set(key, work);

    work.finally(() => {
      this.collection.delete(key);
    });

    return work;
  }
}
