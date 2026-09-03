# Register API extensions before backend.run starts the server.
# main is imported by ovr_server; Python's package initialization handles this safely.
from . import ovr_server  # noqa: F401
