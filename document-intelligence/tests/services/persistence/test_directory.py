"""Tests for persistence services."""

from pathlib import Path

import pytest

from sema4ai_docint.services.persistence import DocumentOperationType
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
        """Test that cache_key_for generates correct cache key format for different operations."""
        service = DirectoryPersistenceService(tmp_path)

        # Test PARSE operation
        cache_key = service.cache_key_for("document.pdf", DocumentOperationType.PARSE)
        assert cache_key == "document.pdf.parse.json"

        # Test SCHEMA operation
        cache_key = service.cache_key_for("invoice_001.pdf", DocumentOperationType.SCHEMA)
        assert cache_key == "invoice_001.pdf.schema.json"

        # Test EXTRACT operation
        cache_key = service.cache_key_for("data.xlsx", DocumentOperationType.EXTRACT)
        assert cache_key == "data.xlsx.extract.json"

    async def test_file_paths_generated_correctly(self, tmp_path):
        """Test that cache files are saved in the correct directory location."""
        cache_dir = tmp_path / "cache"
        service = DirectoryPersistenceService(cache_dir)

        # Generate cache key and save data
        cache_key = service.cache_key_for("document.pdf", DocumentOperationType.PARSE)
        test_data = b'{"test": "data"}'
        await service.save(cache_key, test_data)

        # Verify file exists at expected path
        expected_path = cache_dir / "document.pdf.parse.json"
        assert expected_path.exists()
        assert expected_path.read_bytes() == test_data

    async def test_save_and_load_round_trip(self, tmp_path):
        """Test basic save and load round-trip with bytes data."""
        service = DirectoryPersistenceService(tmp_path)
        test_data = b'{"test": "data", "number": 42}'

        cache_key = service.cache_key_for("test_doc.pdf", DocumentOperationType.PARSE)
        await service.save(cache_key, test_data)
        loaded_data = await service.load(cache_key)

        assert loaded_data == test_data

    async def test_load_returns_none_for_non_existent_key(self, tmp_path):
        """Test that load returns None for non-existent keys."""
        service = DirectoryPersistenceService(tmp_path)

        cache_key = service.cache_key_for("non_existent_doc.pdf", DocumentOperationType.PARSE)
        result = await service.load(cache_key)

        assert result is None

    async def test_save_overwrites_existing_data(self, tmp_path):
        """Test that save overwrites existing data with same key."""
        service = DirectoryPersistenceService(tmp_path)
        first_data = b'{"version": 1}'
        second_data = b'{"version": 2}'

        cache_key = service.cache_key_for("doc.pdf", DocumentOperationType.PARSE)
        await service.save(cache_key, first_data)
        await service.save(cache_key, second_data)
        loaded_data = await service.load(cache_key)

        assert loaded_data == second_data
        assert loaded_data != first_data

    async def test_multiple_documents_cached_independently(self, tmp_path):
        """Test that multiple documents are cached independently."""
        service = DirectoryPersistenceService(tmp_path)
        doc1_data = b'{"doc": "first"}'
        doc2_data = b'{"doc": "second"}'

        cache_key1 = service.cache_key_for("doc1.pdf", DocumentOperationType.PARSE)
        cache_key2 = service.cache_key_for("doc2.pdf", DocumentOperationType.PARSE)

        await service.save(cache_key1, doc1_data)
        await service.save(cache_key2, doc2_data)

        loaded1 = await service.load(cache_key1)
        loaded2 = await service.load(cache_key2)

        assert loaded1 == doc1_data
        assert loaded2 == doc2_data

    async def test_save_empty_data(self, tmp_path):
        """Test saving and loading empty bytes data."""
        service = DirectoryPersistenceService(tmp_path)
        empty_data = b""

        cache_key = service.cache_key_for("empty_doc.pdf", DocumentOperationType.PARSE)
        await service.save(cache_key, empty_data)
        loaded_data = await service.load(cache_key)

        assert loaded_data == empty_data
