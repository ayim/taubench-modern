import os
import shutil
import tempfile
import zipfile
from typing import Any

import yaml
from vcr.persisters.filesystem import FilesystemPersister
from vcr.request import Request as VcrRequest
from vcr.serialize import deserialize as vcr_deserialize
from vcr.serialize import serialize as vcr_serialize
from vcr.serializers import compat as vcr_compat
from yaml.nodes import MappingNode, Node

from core.tests.vcrx.config import CASSETTE_ROOT_DIR


def _deserialize_leniently(cassette_text: str) -> tuple[list[Any], list[Any]]:
    """
    A fallback deserializer for legacy Bedrock cassettes that used custom
    YAML tags for botocore header objects.
    """

    class _LenientLoader(yaml.SafeLoader):
        pass

    def _construct_header_key(loader: yaml.Loader, node: Node) -> str:
        """Converts botocore HeaderKey objects to plain strings."""
        if not isinstance(node, MappingNode):
            raise yaml.constructor.ConstructorError(
                None,
                None,
                f"Expected a mapping node, but got {type(node).__name__}",
                node.start_mark,
            )
        mapping = loader.construct_mapping(node, deep=True)
        return mapping.get("_lower") or mapping.get("_key") or ""

    def _construct_headers_dict(loader: yaml.Loader, node: Node) -> dict[str, Any]:
        """Unwraps botocore HeadersDict into a plain dict."""
        if not isinstance(node, MappingNode):
            raise yaml.constructor.ConstructorError(
                None,
                None,
                f"Expected a mapping node, but got {type(node).__name__}",
                node.start_mark,
            )
        mapping = loader.construct_mapping(node, deep=True)
        return {str(k): v for k, v in mapping.get("_dict", {}).items()}

    _header_key_tag = "tag:yaml.org,2002:python/object:botocore.awsrequest._HeaderKey"
    _headers_dict_tag = "tag:yaml.org,2002:python/object:botocore.awsrequest.HeadersDict"
    _LenientLoader.add_constructor(_header_key_tag, _construct_header_key)
    _LenientLoader.add_constructor(_headers_dict_tag, _construct_headers_dict)

    data_obj = yaml.load(cassette_text, Loader=_LenientLoader)
    interactions = list(data_obj.get("interactions", []) or [])

    requests = []
    responses = []
    for inter in interactions:
        req_dict = inter.get("request", {})
        if not req_dict:
            continue
        try:
            requests.append(VcrRequest._from_dict(req_dict))
            responses.append(vcr_compat.convert_to_bytes(inter.get("response", {})))
        except Exception:
            # If request fails to parse, skip the entire interaction
            continue

    return requests, responses


class ZipArchivePersister:
    """
    Persist cassettes inside ZIP archives.

    Mapping:
        platforms/<platform>/... -> <platform>_cassettes.zip
        everything else          -> all_cassettes.zip
    """

    cassette_library_dir: str = CASSETTE_ROOT_DIR
    default_archive_name: str = "all_cassettes.zip"

    @classmethod
    def _relative(cls, path: str) -> str:
        """Computes the relative path for storing inside the archive."""
        base = os.path.abspath(cls.cassette_library_dir)
        rel = os.path.relpath(os.path.abspath(path), base)
        # Normalize to forward slashes for zip compatibility
        return rel.replace(os.sep, "/")

    @classmethod
    def _select_archive(cls, path: str) -> tuple[str, str]:
        """Determines the correct archive file and the internal path."""
        rel_path = cls._relative(path)
        archive_name = cls.default_archive_name

        if rel_path.startswith("platforms/"):
            parts = rel_path.split("/", 2)
            if len(parts) > 1 and parts[1]:
                platform = parts[1]
                archive_name = f"{platform}_cassettes.zip"

        archive_path = os.path.join(cls.cassette_library_dir, archive_name)
        return archive_path, rel_path

    @classmethod
    def _read_from_archive(cls, archive_path: str, member_path: str) -> bytes | None:
        """Reads a cassette file from a zip archive, returns None if not found."""
        if not os.path.exists(archive_path):
            return None
        try:
            with zipfile.ZipFile(archive_path, mode="r") as zf:
                return zf.read(member_path)
        except KeyError:
            return None  # Cassette not in archive
        except zipfile.BadZipFile as err:
            raise ValueError("Cannot read cassette archive, it may be corrupt.") from err

    @classmethod
    def load_cassette(cls, path: str, serializer: Any) -> Any:
        archive_path, rel_path = cls._select_archive(path)

        data = cls._read_from_archive(archive_path, rel_path)
        if data is not None:
            text = data.decode("utf-8", "ignore")
            try:
                # First attempt: standard VCR deserialize
                return vcr_deserialize(text, serializer)
            except Exception:
                # Fallback: lenient YAML parsing for legacy Bedrock headers
                try:
                    return _deserialize_leniently(text)
                except Exception as err:
                    raise ValueError("Failed to parse cassette with lenient loader.") from err

        # Fallback to filesystem if not found in any archive
        try:
            return FilesystemPersister.load_cassette(path, serializer)
        except Exception as err:
            raise ValueError("Cassette not found in any archive or on the filesystem.") from err

    @classmethod
    def _update_zip_atomically(cls, archive_path: str, member_path: str, data: bytes) -> None:
        """Atomically updates a single file within a zip archive."""
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
                tmp_path = tmp.name

            with (
                zipfile.ZipFile(archive_path, mode="r") as zf_in,
                zipfile.ZipFile(tmp_path, mode="w", compression=zipfile.ZIP_DEFLATED) as zf_out,
            ):
                # Copy all existing files except the one being updated
                for info in zf_in.infolist():
                    if info.filename != member_path:
                        zf_out.writestr(info, zf_in.read(info.filename))
                # Write the new or updated file
                zf_out.writestr(member_path, data)

            shutil.move(tmp_path, archive_path)
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.remove(tmp_path)

    @classmethod
    def save_cassette(cls, path: str, cassette_dict: Any, serializer: Any) -> None:
        archive_path, rel_path = cls._select_archive(path)
        os.makedirs(os.path.dirname(archive_path), exist_ok=True)

        serialized_data = vcr_serialize(cassette_dict, serializer)
        data_bytes = (
            serialized_data.encode("utf-8") if isinstance(serialized_data, str) else serialized_data
        )

        if not os.path.exists(archive_path):
            with zipfile.ZipFile(archive_path, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
                zf.writestr(rel_path, data_bytes)
        else:
            cls._update_zip_atomically(archive_path, rel_path, data_bytes)
