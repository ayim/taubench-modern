from io import BytesIO
from unittest.mock import patch

from fastapi import UploadFile
from langchain.text_splitter import RecursiveCharacterTextSplitter

from sema4ai_agent_server.schema import dummy_model
from sema4ai_agent_server.storage.embed import (
    EmbedRunnable,
    _guess_mimetype,
    convert_to_blob,
)
from tests.unit_tests.fixtures import get_sample_paths
from tests.unit_tests.utils import InMemoryVectorStore


def test_embed_runnable() -> None:
    """Test embed runnable"""
    splitter = RecursiveCharacterTextSplitter()
    runnable = EmbedRunnable(
        text_splitter=splitter, owner_id="TheParrot", model=dummy_model
    )
    # Simulate file data
    file_data = BytesIO(b"test data")
    file_data.seek(0)
    # Create UploadFile object
    file = UploadFile(filename="testfile.txt", file=file_data)

    # Convert the file to blob
    blob = convert_to_blob(file)

    with patch(
        "sema4ai_agent_server.storage.embed.get_vector_store"
    ) as mock_get_vector_store:
        mock_get_vector_store.return_value = InMemoryVectorStore()
        ids = runnable.invoke(blob)

    assert len(ids) == 1


def test_mimetype_guessing() -> None:
    """Verify mimetype guessing for all fixtures."""
    name_to_mime = {}
    for file in sorted(get_sample_paths()):
        data = file.read_bytes()
        name_to_mime[file.name] = _guess_mimetype(file.name, data)

    assert {
        "sample.docx": (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ),
        "sample.epub": "application/epub+zip",
        "sample.html": "text/html",
        "sample.odt": "application/vnd.oasis.opendocument.text",
        "sample.pdf": "application/pdf",
        "sample.rtf": "application/rtf",
        "sample.txt": "text/plain",
    } == name_to_mime
