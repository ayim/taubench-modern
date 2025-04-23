import argparse
import os
import pprint
import sys

import pkg_resources
from PyInstaller.building.api import COLLECT, EXE, PYZ
from PyInstaller.building.build_main import Analysis
from PyInstaller.log import logger
from PyInstaller.utils.hooks import (
    collect_all,
    collect_data_files,
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

# Log arguments using PyInstaller's logging system
logger.info("=== Build Arguments ===")
logger.info(f"Debug mode: {options.debug}")
logger.info(f"Onefile mode: {options.onefile}")
logger.info(f"Output name: {options.name}")
logger.info("=====================")

# Dynamically discover agent architecture packages
agent_arch_packages = [
    dist.key
    for dist in pkg_resources.working_set
    if dist.key.startswith("agent-platform-architectures-")
]
logger.info("=== Found Agent Architecture Packages ===")
logger.info(",".join(agent_arch_packages))
logger.info("========================================")

# Build metadata and hidden imports for agent architectures
agent_arch_metadata = []
agent_arch_imports = []
for package in agent_arch_packages:
    agent_arch_metadata.extend(copy_metadata(package))
    agent_arch_imports.append(
        package.replace(
            "agent-platform-architectures-",
            "agent_platform.architectures.",
        )
    )

logger.info("=== Analyzing Imports ===")
logger.info("Starting Analysis phase...")

# Log each major collection step
# logger.info("Collecting chromadb dependencies...")
# chromadb_datas, chromadb_binaries, chromadb_hiddenimports = collect_all("chromadb")
logger.info("Collecting tiktoken dependencies...")
tiktoken_binaries = collect_data_files("tiktoken")
tiktoken_hiddenimports = ["tiktoken_ext"]  # Only need the extension module

# Collect submodules with logging
# logger.info("Collecting chromadb submodules...")
# chromadb_submodules = collect_submodules(
#     "chromadb", filter=lambda name: not name.startswith("chromadb.test")
# )
# logger.info("Collecting chromadb.db submodules...")
# chromadb_db_submodules = collect_submodules(
#     "chromadb.db", filter=lambda name: not name.startswith("chromadb.db.test")
# )
# logger.info("Collecting chromadb.migrations submodules...")
# chromadb_migrations_submodules = collect_submodules("chromadb.migrations")
logger.info("Collecting tiktoken_ext submodules...")
tiktoken_ext_submodules = collect_submodules("tiktoken_ext")
logger.info("Collecting all for psycopg...")
psycopg_datas, psycopg_binaries, psycopg_hiddenimports = collect_all("psycopg")

# Add explicit psycopg binary imports - these are the core components needed
psycopg_hiddenimports.extend(
    [
        "psycopg.binary",  # Binary package support
        "psycopg._impl",  # Core implementation
        "psycopg._impl.adapt",  # Type adaptation
        "psycopg._impl.cursor",  # Cursor implementation
        "psycopg._impl.connection",  # Connection handling
        "psycopg.pool",  # Connection pooling support
    ]
)

logger.info("Starting main Analysis...")
a = Analysis(
    ["src/agent_platform/server/server.py"],
    pathex=["core/src", "architectures/default/src", "server/src"],
    binaries=[
        # *chromadb_binaries,
        *tiktoken_binaries,
        *psycopg_binaries,
    ],
    datas=[
        (
            "src/agent_platform/server/migrations",
            "agent_platform/server/migrations",
        ),
        # TODO: auto add a prompts dir for each architecture automatically?
        (
            "../architectures/default/src/agent_platform/architectures/default/prompts",
            "agent_platform/architectures/default/prompts",
        ),
        *agent_arch_metadata,
        # *chromadb_datas,
        # *tiktoken_datas,
        *psycopg_datas,
        ("LICENSE", "."),
    ],
    hiddenimports=[
        "pydantic.deprecated.decorator",
        "chromadb.utils.embedding_functions.onnx_mini_lm_l6_v2",
        "onnxruntime",
        "agent_platform.architectures",
        *agent_arch_imports,
        # Chromadb imports commented out as they're not currently used
        # *chromadb_submodules,
        # *chromadb_db_submodules,
        # *chromadb_migrations_submodules,
        # "chromadb.migrations.embeddings_queue",
        # *chromadb_hiddenimports,
        *tiktoken_hiddenimports,
        "tiktoken_ext",
        *tiktoken_ext_submodules,
        *psycopg_hiddenimports,
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # in v1 we excluded nltk and magic but those are not installed in v2
    # so they are not needed
    excludes=[],
    noarchive=False,
    optimize=0,
)

logger.info("=== Packaging Components ===")
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
    "bootloader_ignore_signals": True,
    "strip": False,
    "upx": True,
    "console": True,
    "disable_windowed_traceback": False,
    "argv_emulation": False,
    "target_arch": None,
    "codesign_identity": os.environ.get("MACOS_SIGNING_CERT_NAME", "-"),
    "entitlements_file": "./entitlements.mac.plist"
    if os.path.exists("./entitlements.mac.plist")
    else None,
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

logger.info("=== Building Executable ===")
pp = pprint.PrettyPrinter(indent=2)
logger.debug(f"Building executable with the following args:\n{pp.pformat(exe_args)}")
logger.debug(
    f"Building executable with the following kwargs:\n{pp.pformat(exe_kwargs)}"
)

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
