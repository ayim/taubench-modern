type Action = { type: 'tenants_selection'; tenants: { name: string; url: string }[] };

export class RequestError extends Error {
  public status: number;
  public action?: Action;

  constructor(status: number, message: string, action?: Action) {
    super(message);
    this.name = 'RequestError';
    this.status = status;
    this.action = action;
  }
}
