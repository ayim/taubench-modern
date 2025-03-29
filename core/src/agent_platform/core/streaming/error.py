from agent_platform.core.streaming.delta import StreamingDelta


class StreamingError(Exception):
    """Raised when there is an error streaming message deltas to downstream consumers.

    Arguments:
        message: A string describing the error that occurred
        delta_object: Optional StreamingDelta object that caused the error
    """

    delta_object: StreamingDelta | None = None
    """The delta object that caused the error."""

    def __init__(self, message: str, delta_object: StreamingDelta | None = None):
        super().__init__(message)
        self.delta_object = delta_object
