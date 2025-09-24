import sys
from pathlib import Path

import structlog
from fastapi.routing import Mount

from agent_platform.server.api.private_v2 import PRIVATE_V2_PREFIX
from agent_platform.server.api.public_v2 import PUBLIC_V2_PREFIX

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


def find_mounted_app(root, mount_path: str):
    for r in root.router.routes:
        if isinstance(r, Mount) and r.path.rstrip("/") == mount_path.rstrip("/"):
            return r.app
    return None


def dump_schema(app, out_path: str, servers_url: str):
    import json

    schema = app.openapi()
    schema["servers"] = [{"url": servers_url}]
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(json.dumps(schema, indent=2), encoding="utf-8")
    print(f"Wrote {out_path}")


def print_openapi_spec(public_path: str, private_path: str, should_exit: bool = True):
    from agent_platform.server.app import create_app

    root = create_app()

    public_app = find_mounted_app(root, PUBLIC_V2_PREFIX)
    private_app = find_mounted_app(root, PRIVATE_V2_PREFIX)

    dump_schema(public_app, public_path, PUBLIC_V2_PREFIX)
    dump_schema(private_app, private_path, PRIVATE_V2_PREFIX)

    if should_exit:
        sys.exit(0)
