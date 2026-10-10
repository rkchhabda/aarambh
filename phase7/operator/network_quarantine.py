"""Network quarantine enforcement for Phase 7 Offline Operator Application.

Milestone 4.12: Strictly blocks external network calls at the runtime layer:
- socket.socket.connect
- socket.create_connection
- httpx.Client.send
- urllib.request.urlopen
- requests.Session.send (if installed)
- asyncio.BaseEventLoop.create_connection

Any attempted network operation:
- fails immediately;
- creates a sanitized audit record;
- displays NETWORK_OPERATION_BLOCKED_BY_INTERNAL_OFFLINE_POLICY;
- performs zero retry;
- preserves fail-closed read-only application state.
"""

import asyncio
from datetime import datetime, timezone
import inspect
from pathlib import Path
import socket
from typing import Any, Callable, Dict, List, Optional
from unittest.mock import patch
import urllib.request

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

NETWORK_BLOCKED_MESSAGE = "NETWORK_OPERATION_BLOCKED_BY_INTERNAL_OFFLINE_POLICY"


class NetworkOperationBlockedError(RuntimeError):
    """Raised whenever any outbound network communication is attempted."""
    pass


class NetworkQuarantineManager:
    """Manages OS/runtime network interceptors and sanitized audit logging."""

    def __init__(self, audit_callback: Optional[Callable[[Dict[str, Any]], None]] = None) -> None:
        self.audit_callback = audit_callback
        self.blocked_attempts: List[Dict[str, Any]] = []
        self._patches: List[Any] = []
        self._active: bool = False

    @property
    def is_active(self) -> bool:
        return self._active

    def _record_blocked_attempt(self, operation: str, target: str = "UNKNOWN_TARGET") -> None:
        """Create sanitized audit record of blocked network attempt."""
        caller_frame = inspect.currentframe()
        caller_info = "unknown"
        if caller_frame and caller_frame.f_back and caller_frame.f_back.f_back:
            frame = caller_frame.f_back.f_back
            caller_info = f"{frame.f_code.co_filename}:{frame.f_lineno} ({frame.f_code.co_name})"

        record: Dict[str, Any] = {
            "event": "NETWORK_OPERATION_BLOCKED",
            "status": "BLOCKED",
            "message": NETWORK_BLOCKED_MESSAGE,
            "operation": operation,
            "target": str(target)[:120],  # sanitized length bound
            "caller": caller_info,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "retry_performed": False,
            "read_only_preserved": True,
        }
        self.blocked_attempts.append(record)

        if self.audit_callback:
            try:
                self.audit_callback(record)
            except Exception:
                pass

    def _block_socket_connect(self, *args, **kwargs) -> None:
        target = args[1] if len(args) > 1 else kwargs.get("address", "socket_target")
        self._record_blocked_attempt("socket.socket.connect", str(target))
        raise NetworkOperationBlockedError(NETWORK_BLOCKED_MESSAGE)

    def _block_socket_create_connection(self, *args, **kwargs) -> None:
        target = args[0] if len(args) > 0 else kwargs.get("address", "create_connection_target")
        self._record_blocked_attempt("socket.create_connection", str(target))
        raise NetworkOperationBlockedError(NETWORK_BLOCKED_MESSAGE)

    def _block_httpx_send(self, *args, **kwargs) -> None:
        req = args[1] if len(args) > 1 else kwargs.get("request")
        url = getattr(req, "url", "httpx_url") if req else "httpx_url"
        self._record_blocked_attempt("httpx.Client.send", str(url))
        raise NetworkOperationBlockedError(NETWORK_BLOCKED_MESSAGE)

    def _block_urllib_urlopen(self, *args, **kwargs) -> None:
        url = args[0] if len(args) > 0 else kwargs.get("url", "urllib_url")
        self._record_blocked_attempt("urllib.request.urlopen", str(url))
        raise NetworkOperationBlockedError(NETWORK_BLOCKED_MESSAGE)

    def _block_requests_send(self, *args, **kwargs) -> None:
        req = args[1] if len(args) > 1 else kwargs.get("request")
        url = getattr(req, "url", "requests_url") if req else "requests_url"
        self._record_blocked_attempt("requests.Session.send", str(url))
        raise NetworkOperationBlockedError(NETWORK_BLOCKED_MESSAGE)

    async def _block_async_create_connection(self, *args, **kwargs) -> None:
        host = kwargs.get("host", "async_host")
        port = kwargs.get("port", "async_port")
        self._record_blocked_attempt("asyncio.create_connection", f"{host}:{port}")
        raise NetworkOperationBlockedError(NETWORK_BLOCKED_MESSAGE)

    def activate(self) -> None:
        """Activate all network interceptor patches."""
        if self._active:
            return

        self._patches = [
            patch("socket.socket.connect", side_effect=self._block_socket_connect),
            patch("socket.create_connection", side_effect=self._block_socket_create_connection),
            patch("urllib.request.urlopen", side_effect=self._block_urllib_urlopen),
            patch("asyncio.BaseEventLoop.create_connection", side_effect=self._block_async_create_connection),
        ]

        if HAS_HTTPX:
            self._patches.append(patch("httpx.Client.send", side_effect=self._block_httpx_send))

        if HAS_REQUESTS:
            self._patches.append(patch("requests.Session.send", side_effect=self._block_requests_send))

        for p in self._patches:
            p.start()

        self._active = True

    def deactivate(self) -> None:
        """Deactivate all patches (for cleanup during testing)."""
        if not self._active:
            return

        for p in reversed(self._patches):
            try:
                p.stop()
            except Exception:
                pass
        self._patches.clear()
        self._active = False

    def __enter__(self) -> "NetworkQuarantineManager":
        self.activate()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.deactivate()
