export class RequestError extends Error {
  public status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = 'RequestError';
    this.status = status;
  }
}
