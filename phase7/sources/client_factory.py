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

    Canonical factory interface requiring:
    - download_folder: absolute pathlib.Path strictly outside the Git repository
    - server: strict boolean True
    - timeout: integer exactly 15 seconds
    """
    if not isinstance(download_folder, Path):
        raise TypeError(f"download_folder must be a pathlib.Path, got: {type(download_folder).__name__}")

    if not download_folder.is_absolute():
        raise ValueError(f"download_folder must be an absolute path, got: '{download_folder}'")

    from phase7.sources.authorization import find_repo_root

    resolved_folder = download_folder.resolve()
    repo = find_repo_root().resolve()
    if resolved_folder == repo or repo in resolved_folder.parents:
        raise ValueError(
            f"download_folder '{resolved_folder}' cannot reside inside Git repository '{repo}'."
        )

    if not isinstance(server, bool) or server is not True:
        raise ValueError(f"server parameter must be strictly boolean True for governed pilot, got: {server}")

    if type(timeout) is not int or timeout != 15:
        raise ValueError(f"timeout parameter must be strictly integer 15 for governed pilot, got: {timeout}")

    if not download_folder.exists():
        download_folder.mkdir(parents=True, exist_ok=True)

    try:
        from nse import NSE
    except ImportError as exc:
        raise ImportError(
            f"The 'nse' package is not installed in the active environment: {exc}"
        ) from exc

    return NSE(
        download_folder=download_folder,
        server=server,
        timeout=timeout,
    )
