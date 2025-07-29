type Success<TSuccess> = { success: true; data: TSuccess };
type Failure<TError> = {
  success: false;
  error: TError;
};

export type Result<TSuccess, TError = { code: string; message: string }> = Success<TSuccess> | Failure<TError>;
