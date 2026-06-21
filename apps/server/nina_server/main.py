import logging
import os
import signal
import sys

import uvicorn
from nina_core.config import (
    get_config_dir,
    get_config_path,
    get_token_path,
    load_effective_config,
    read_token,
)

from .app import create_app
from .logging_config import configure_logging, resolve_log_level
from .runtime import DaemonRuntime, apply_runtime_config


def main() -> None:
    profile = os.environ.get("NINA_PROFILE", "default")
    config_dir = get_config_dir(profile)
    token_path = get_token_path(config_dir)
    config_path = get_config_path(config_dir)
    if not config_path.exists():
        print("Run 'nina init' first.", file=sys.stderr)
        return

    os.environ["NINA_TOKEN"] = read_token(token_path)
    config = load_effective_config(config_dir)
    log_config = configure_logging(config.log_level)
    logging.getLogger(__name__).info("nina.daemon event=starting profile=%s", profile)
    application = create_app()
    apply_runtime_config(application, config_dir, config)
    runtime = application.state.runtime
    if not isinstance(runtime, DaemonRuntime):
        raise RuntimeError("daemon runtime was not initialized")
    runtime.write_runtime_state()
    runtime.start_services()

    def _shutdown(*_args: object) -> None:
        runtime.shutdown_services()

    if os.name != "nt":
        signal.signal(signal.SIGTERM, _shutdown)
        signal.signal(signal.SIGINT, _shutdown)

    try:
        uvicorn.run(
            application,
            host=config.daemon_host,
            port=config.daemon_port,
            log_config=log_config,
            log_level=resolve_log_level(config.log_level),
        )
    finally:
        runtime.shutdown_services()


if __name__ == "__main__":
    main()
