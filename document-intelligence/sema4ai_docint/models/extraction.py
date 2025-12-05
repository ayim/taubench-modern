from typing import Any

from pydantic import BaseModel


class ExtractionResult(BaseModel):
    """
    The extracted output from a document. Optionally includes citations which give
    grounding to where in the original document the values in the output were found.

    Attributes:
        results (dict[str, Any]): The extracted data from the document. The structure
            of this dictionary depends on the extraction schema used and contains
            the actual extracted information organized by field names.
        citations (dict[str, Any] | None): Optional citation information that maps
            extracted data to its source locations within the document. This can
            include page numbers, coordinates, or other positional metadata.
            Defaults to None if no citation information is available.
    """

    results: dict[str, Any]
    citations: dict[str, Any] | None = None
