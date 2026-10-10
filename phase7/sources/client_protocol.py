"""Client protocol definition for NSE retrieval engines.

Enables dependency injection and mocking without importing external libraries at module load.
"""

from typing import Any, Dict, List, Optional, Protocol, runtime_checkable


@runtime_checkable
class NSEClientProtocol(Protocol):
    """Protocol matching the public interface of upstream NSE clients."""

    def fetch_equity_historical_data(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        interval: str = "1d",
    ) -> Any:
        ...

    def equityQuote(self, symbol: str) -> Dict[str, Any]:
        ...

    def status(self) -> Dict[str, Any]:
        ...

    def listEquityStocksByIndex(self, index: str = "NIFTY 50") -> Dict[str, Any]:
        ...

    def actions(
        self,
        segment: str = "equities",
        symbol: Optional[str] = None,
        from_date: Optional[Any] = None,
        to_date: Optional[Any] = None,
    ) -> List[Dict[str, Any]]:
        ...

    def exit(self) -> None:
        ...


@runtime_checkable
class NSEClientFactoryProtocol(Protocol):
    """Protocol matching the canonical client factory signature."""

    def __call__(
        self,
        download_folder: Any,
        server: bool = True,
        timeout: int = 15,
    ) -> NSEClientProtocol:
        ...
