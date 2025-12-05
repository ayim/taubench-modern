"""Tests for persistence services."""

from pathlib import Path

import pytest

from sema4ai_docint.services.persistence.directory import DirectoryPersistenceService


@pytest.mark.asyncio
class TestDirectoryPersistenceService:
    """Test suite for DirectoryPersistenceService."""

    async def test_directory_creation_with_str(self, tmp_path):
        """Test that directory is created when initialized with str path."""
        cache_dir = str(tmp_path / "cache")
        service = DirectoryPersistenceService(cache_dir)

        assert Path(cache_dir).exists()
        assert Path(cache_dir).is_dir()
        assert service._directory == Path(cache_dir)

    async def test_directory_creation_with_path(self, tmp_path):
        """Test that directory is created when initialized with Path object."""
        cache_dir = tmp_path / "cache"
        service = DirectoryPersistenceService(cache_dir)

        assert cache_dir.exists()
        assert cache_dir.is_dir()
        assert service._directory == cache_dir

    async def test_cache_key_for_generates_correct_format(self, tmp_path):
        """Test that _cache_key_for generates correct cache key format."""
        service = DirectoryPersistenceService(tmp_path)

        cache_key = service._cache_key_for("document.pdf")
        assert cache_key == "document.pdf.parse.json"

        cache_key = service._cache_key_for("invoice_001")
        assert cache_key == "invoice_001.parse.json"

    async def test_path_for_generates_correct_file_paths(self, tmp_path):
        """Test that _path_for generates correct file paths from cache keys."""
        cache_dir = tmp_path / "cache"
        service = DirectoryPersistenceService(cache_dir)

        path = service._path_for("document.pdf")
        expected = cache_dir / "document.pdf.parse.json"
        assert path == expected

    async def test_save_and_load_round_trip(self, tmp_path):
        """Test basic save and load round-trip with bytes data."""
        service = DirectoryPersistenceService(tmp_path)
        test_data = b'{"test": "data", "number": 42}'

        await service.save("test_doc.pdf", test_data)
        loaded_data = await service.load("test_doc.pdf")

        assert loaded_data == test_data

    async def test_load_returns_none_for_non_existent_key(self, tmp_path):
        """Test that load returns None for non-existent keys."""
        service = DirectoryPersistenceService(tmp_path)

        result = await service.load("non_existent_doc.pdf")

        assert result is None

    async def test_save_overwrites_existing_data(self, tmp_path):
        """Test that save overwrites existing data with same key."""
        service = DirectoryPersistenceService(tmp_path)
        first_data = b'{"version": 1}'
        second_data = b'{"version": 2}'

        await service.save("doc.pdf", first_data)
        await service.save("doc.pdf", second_data)
        loaded_data = await service.load("doc.pdf")

        assert loaded_data == second_data
        assert loaded_data != first_data

    async def test_multiple_documents_cached_independently(self, tmp_path):
        """Test that multiple documents are cached independently."""
        service = DirectoryPersistenceService(tmp_path)
        doc1_data = b'{"doc": "first"}'
        doc2_data = b'{"doc": "second"}'

        await service.save("doc1.pdf", doc1_data)
        await service.save("doc2.pdf", doc2_data)

        loaded1 = await service.load("doc1.pdf")
        loaded2 = await service.load("doc2.pdf")

        assert loaded1 == doc1_data
        assert loaded2 == doc2_data

    async def test_save_empty_data(self, tmp_path):
        """Test saving and loading empty bytes data."""
        service = DirectoryPersistenceService(tmp_path)
        empty_data = b""

        await service.save("empty_doc.pdf", empty_data)
        loaded_data = await service.load("empty_doc.pdf")

        assert loaded_data == empty_data
