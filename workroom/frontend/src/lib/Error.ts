type Action = { type: 'tenants_selection'; tenants: { name: string; url: string }[] };

export class RequestError extends Error {
  public status: number;
  public action?: Action;
  public details?: string;

  constructor(status: number, message: string, action?: Action, details?: string) {
    super(message);
    this.name = 'RequestError';
    this.status = status;
    this.action = action;
    this.details = details;
  }
}
