class TransportError(Exception):
    """Base class for transport errors."""

    pass


class TransportMissingBaseUrlError(TransportError):
    """Error raised when a transport cannot be initialized because the base URL is missing."""

    def __init__(self):
        super().__init__("Transport base URL is missing")


class TransportNotConnectedError(TransportError):
    """Error raised when a transport is not connected."""

    def __init__(self):
        super().__init__("Transport is not connected")


class TransportResponseConversionError(TransportError):
    """Error raised when a problem occurs when converting a response to a ResponseMessage."""

    def __init__(self, response_text: str):
        self.response_text = response_text
        super().__init__(f"Could not convert the server response to JSON: {response_text}")


class TransportThreadIdRequiredError(TransportError):
    """Error raised when a transport requires a thread ID but none was provided."""

    def __init__(self):
        super().__init__("Thread ID is required to get a file")


class TransportFileRetrievalError(TransportError):
    """Error raised when a transport cannot retrieve a file."""

    def __init__(self, file_name: str, message: str):
        self.file_name = file_name
        self.message = message
        super().__init__(f"Failed to retrieve file {file_name}: {message}")
