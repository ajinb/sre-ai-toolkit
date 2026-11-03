"""sre-ai-toolkit — curated AI-assisted scripts for platform and reliability engineers."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("sre-ai-toolkit")
except PackageNotFoundError:  # running from a source tree without an install
    __version__ = "0.0.0.dev0"
