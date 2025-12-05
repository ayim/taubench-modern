import struct

import siphash


def blueprint_hash(blueprint_bytes: bytes) -> str:
    """
    Calculate the blueprint hash using SipHash with RCC's fixed seeds.

    This replicates RCC's BlueprintHash function:
    - Uses SipHash with seeds 9007199254740993, 2147483647
    - Returns 16-character hexadecimal string
    """
    # RCC's fixed seeds from Sipit function
    seed1 = 9007199254740993
    seed2 = 2147483647

    # Convert the two uint64 seeds to a 16-byte key in little-endian format
    # This matches how Go's siphash.Hash(left, right, body) works
    key = struct.pack("<QQ", seed1, seed2)

    # Calculate SipHash using the class-based API
    hasher = siphash.SipHash_2_4(key, blueprint_bytes)
    hash_value = hasher.hash()

    # Format as 16-character hex string (matching RCC's Textual function)
    return f"{hash_value:016x}"
