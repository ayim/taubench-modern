# -*- mode: python ; coding: utf-8 -*-

import argparse
import sys

from PyInstaller.building.api import COLLECT, EXE, PYZ
from PyInstaller.building.build_main import Analysis
from PyInstaller.utils.hooks import (
    collect_all,
    collect_submodules,
    copy_metadata,
)

sys.setrecursionlimit(sys.getrecursionlimit() * 5)

# Parse args to the specfile
parser = argparse.ArgumentParser()
parser.add_argument("--debug", action="store_true")
parser.add_argument("--onefile", action="store_true")
parser.add_argument("--name", type=str, default="agent-server")
options = parser.parse_args()

chromadb_datas, chromadb_binaries, chromadb_hiddenimports = collect_all("chromadb")
tiktoken_datas, tiktoken_binaries, tiktoken_hiddenimports = collect_all("tiktoken")


a = Analysis(
    ["sema4ai_agent_server/server.py"],
    pathex=[],
    binaries=[*chromadb_binaries, *tiktoken_binaries],
    datas=[
        ("sema4ai_agent_server/migrations", "sema4ai_agent_server/migrations"),
        *copy_metadata("agent-architecture"),
        *copy_metadata("agent-architecture-openai-plan-execute"),
        *copy_metadata("agent-architecture-claude-tools"),
        *chromadb_datas,
        *tiktoken_datas,
    ],
    hiddenimports=[
        "pydantic.deprecated.decorator",
        "chromadb.utils.embedding_functions.onnx_mini_lm_l6_v2",
        "onnxruntime",
        "agent_architecture_default",
        "agent_architecture_openai_plan_execute",
        "agent_architecture_claude_tools",
        *collect_submodules("chromadb"),
        *collect_submodules("chromadb.db"),
        *collect_submodules("chromadb.migrations"),
        "chromadb.migrations.embeddings_queue",
        *chromadb_hiddenimports,
        *tiktoken_hiddenimports,
        "tiktoken_ext",
        *collect_submodules("tiktoken_ext"),
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

# Executable args
exe_args = [pyz, a.scripts]
if options.onefile:
    exe_args.append(a.binaries)
    exe_args.append(a.datas)
if options.debug:
    exe_args.append([("v", None, "OPTION")])
else:
    exe_args.append([])

# Executable kwargs
exe_kwargs = {
    "name": options.name,
    "bootloader_ignore_signals": False,
    "strip": False,
    "upx": True,
    "console": True,
    "disable_windowed_traceback": False,
    "argv_emulation": False,
    "target_arch": None,  # TODO: Handle MacOSx somehow
    "codesign_identity": None,  # TODO: Add signing for CI
    "entitlements_file": None,
}
if options.debug:
    exe_kwargs["debug"] = True
else:
    exe_kwargs["debug"] = False
if options.onefile:
    exe_kwargs["upx_exclude"] = []
    exe_kwargs["runtime_tmpdir"] = None
else:
    exe_kwargs["exclude_binaries"] = True

exe = EXE(
    *exe_args,
    **exe_kwargs,
)

if not options.onefile:
    coll = COLLECT(
        exe,
        a.binaries,
        a.datas,
        strip=False,
        upx=True,
        upx_exclude=[],
        name=options.name,
    )
