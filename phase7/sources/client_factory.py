"""Explicit runtime client factory for the nse package.

Strictly isolates the third-party nse import to runtime invocation only.
Never imports nse at module load time.
"""

from pathlib import Path
from typing import Optional
from phase7.sources.client_protocol import NSEClientProtocol


def create_real_nse_client(
    download_folder: Path,
    server: bool = True,
    timeout: int = 15,
) -> NSEClientProtocol:
    """Create a real NSE client instance inside an explicitly authorized execution context.

    Imports `nse` locally to prevent top-level module import side effects or copyleft linkage.
    """
    folder = Path(download_folder)
    if not folder.exists():
        folder.mkdir(parents=True, exist_ok=True)

    try:
        from nse import NSE
    except ImportError as exc:
        raise ImportError(
            f"The 'nse' package is not installed in the active environment: {exc}"
        ) from exc

    return NSE(
        download_folder=folder,
        server=server,
        timeout=timeout,
    )
