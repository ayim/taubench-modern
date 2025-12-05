import base64
import hashlib
import json
from collections import Counter
from typing import Any

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


class ExtractionSchema:
    layout_name: str
    schema: str

    def __init__(self, layout_name: str, schema: str):
        self.layout_name = layout_name
        self.schema = schema


def match_known_schema(
    known_schemas: list[ExtractionSchema], new_schema_json: str, threshold: float = 0.9
) -> ExtractionSchema | None:
    """
    Match a new schema to a list of known schemas.

    Args:
        known_schemas (list[ExtractionSchema]): List of known schemas.
        new_schema_json (str): The new schema to match.
        threshold (float): The threshold for a match.

    Returns:
        The best match, or None if no match exceeds the threshold
    """
    # Vectorize the known schemas
    vectoriser = TfidfVectorizer(token_pattern=r"\S+")
    x_ref = vectoriser.fit_transform([schema.schema for schema in known_schemas])

    # Vectorize the new schema
    tok = _schema_to_token_string(new_schema_json)
    vec = vectoriser.transform([" ".join(tok)])

    # Compute the similarity scores
    sims = cosine_similarity(vec, x_ref)[0]  # array of scores vs refs

    # Find the best match
    max_val, max_idx = sims.max(), sims.argmax()
    if max_val > threshold:
        return known_schemas[max_idx]

    # No match that exceeds the threshold was found
    return None


TYPE_MAP: dict[str, str] = {  # primitive to single-char code
    "string": "S",
    "number": "N",
    "integer": "I",
    "boolean": "B",
    "null": "Z",
}


def _name_hash(names: list[str], buckets: int = 64) -> str:
    """
    Deterministic tiny hash of sorted, normalized field names.
    Collapses to one base64 char => weak but non-zero name influence.
    """
    normalized = [name.lower() for name in sorted(names)]
    digest = hashlib.blake2b((",".join(normalized)).encode(), digest_size=1).digest()
    return base64.b64encode(digest).decode()[:1]  # one char, 64-bucket


def schema_tokens(
    schema: dict[str, Any], *, include_name_hash: bool = True, _memo=None
) -> list[str]:
    """
    Recursively emit multiset-based tokens for *every* object / array node.

    Parameters
    ----------
    schema (dict): Fully inlined JSON Schema (Draft 07+).
    include_name_hash (bool): If True, add a 1-char hash suffix to object tokens so
        {a,b,c} ≠ {d,e,f} even when type profiles match.
    """
    if _memo is None:
        _memo = set()  # prevent cycles on recursive refs

    # Avoid revisiting the same node (idempotency for shared subschemas)
    sid = id(schema)
    if sid in _memo:
        return []
    _memo.add(sid)

    t = schema.get("type")

    # -------- PRIMITIVES ---------------------------------------------------
    if t in TYPE_MAP:
        return [TYPE_MAP[t]]  # type: ignore

    # -------- ARRAYS -------------------------------------------------------
    if t == "array":
        item_schema = schema.get("items", {"type": "any"})
        inner_tokens = schema_tokens(item_schema, include_name_hash=include_name_hash, _memo=_memo)
        return [f"A<{inner_tokens[0]}>", *inner_tokens]  # emit self + recurse

    # -------- OBJECTS ------------------------------------------------------
    if t == "object":
        props: dict[str, Any] = schema.get("properties", {})
        # 1. multiset of CHILD **types** (not names)
        type_counts = Counter(
            TYPE_MAP.get(v.get("type", "any"), "?")
            if v.get("type") != "array"
            else "A"  # collapse arrays-of-??? to 'A' here
            for v in props.values()
        )

        # build the {S²,I¹} compact string
        inner_descr = ",".join(
            f"{k}{'' if c == 1 else str(c)}" for k, c in sorted(type_counts.items())
        )
        token = f"O{{{inner_descr}}}"

        # 2. optional tiny hash of **names** to distinguish a,b,c vs d,e,f
        if include_name_hash:
            token += f"#{_name_hash(list(props))}"

        # recurse into children
        child_tokens = []
        for v in props.values():
            child_tokens += schema_tokens(v, include_name_hash=include_name_hash, _memo=_memo)
        return [token, *child_tokens]

    return ["?"]  # treat unknown / anyOf / oneOf as wildcard


def _schema_to_token_string(schema_json: str, include_name_hash: bool = True) -> str:
    schema = json.loads(schema_json)
    tokens = schema_tokens(schema, include_name_hash=include_name_hash)
    return " ".join(tokens)
