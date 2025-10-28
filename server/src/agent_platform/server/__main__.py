# ruff: noqa
DEBUG_STARTUP = False
import time

start_time = time.monotonic()
import sys
import agent_platform.server

if __name__ == "__main__":
    try:
        agent_platform.server.main(run_server=not DEBUG_STARTUP)
    finally:
        if DEBUG_STARTUP:
            import psutil

            print(f"Server took {time.monotonic() - start_time:.2f} seconds to start")
            print(f"Number of modules loaded: {len(sys.modules)}")
            print(f"RAM memory usage: {psutil.Process().memory_info().rss / 1024 / 1024:.2f} MB")
