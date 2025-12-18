# ruff: noqa
DEBUG_STARTUP = False
import time

start_time = time.monotonic()

# Config a Path to dump traces
# import os
# os.environ["SEMA4AI_AGENT_SERVER_AGENT_TRACE_DIR"] = "c:/temp/traces"

import sys
import agent_platform.server


RUN_AS_STUDIO = False
RUN_WITH_POSTGRES = False


if __name__ == "__main__":
    if RUN_WITH_POSTGRES:
        import os

        os.environ["SEMA4AI_AGENT_SERVER_DB_TYPE"] = "postgres"
        os.environ["POSTGRES_HOST"] = "localhost"
        os.environ["POSTGRES_DB"] = "agents"
        os.environ["POSTGRES_USER"] = "agents"
        os.environ["POSTGRES_PASSWORD"] = "agents"
        os.environ["POSTGRES_PORT"] = "5432"

    if RUN_AS_STUDIO:
        sys.argv = [
            "",
            "--host",
            "127.0.0.1",
            "--port",
            "58885",
            "--use-data-dir-lock",
            "--kill-lock-holder",
        ]
    try:
        agent_platform.server.main(run_server=not DEBUG_STARTUP)
    finally:
        if DEBUG_STARTUP:
            import psutil

            print(f"Server took {time.monotonic() - start_time:.2f} seconds to start")
            print(f"Number of modules loaded: {len(sys.modules)}")
            print(f"RAM memory usage: {psutil.Process().memory_info().rss / 1024 / 1024:.2f} MB")
