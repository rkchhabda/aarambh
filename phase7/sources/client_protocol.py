"""Client protocol definition for NSE retrieval engines.

Enables dependency injection and mocking without importing external libraries at module load.
"""

from datetime import datetime
import inspect
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable


@runtime_checkable
class NSEClientProtocol(Protocol):
    """Protocol matching the public interface of upstream NSE clients."""

    def fetch_equity_historical_data(
        self,
        symbol: str,
        start_date: str = ...,
        end_date: str = ...,
        interval: str = "1d",
        **kwargs: Any,
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


def call_canonical_historical_retrieval(
    client: Any,
    symbol: str,
    start_date: str,
    end_date: str,
    interval: str = "1d",
) -> Any:
    """Invoke the historical retrieval method on the injected client.

    Preserves exact governed parameters:
    - symbol
    - start_date
    - end_date
    - interval

    Statically adapts between upstream nse==4.0.1 parameter conventions
    (symbol, from_date, to_date, series='EQ') and governed protocol conventions
    (symbol, start_date, end_date, interval='1d') without runtime side effects,
    without substituting date.today(), and without broadening the date range.
    """
    if not hasattr(client, "fetch_equity_historical_data"):
        if hasattr(client, "get_historical_data"):
            return client.get_historical_data(symbol=symbol, start=start_date, end=end_date)
        raise AttributeError(
            f"Injected client '{type(client).__name__}' does not implement fetch_equity_historical_data."
        )

    method = getattr(client, "fetch_equity_historical_data")
    try:
        sig = inspect.signature(method)
        params = sig.parameters
    except (ValueError, TypeError):
        params = {}

    # Upstream nse==4.0.1 defines:
    # fetch_equity_historical_data(symbol, from_date=None, to_date=None, series='EQ')
    if "from_date" in params and "start_date" not in params:
        from_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
        to_dt = datetime.strptime(end_date, "%Y-%m-%d").date()
        kwargs: Dict[str, Any] = {
            "symbol": symbol,
            "from_date": from_dt,
            "to_date": to_dt,
        }
        if "series" in params:
            kwargs["series"] = "EQ"
        return method(**kwargs)

    # Governed protocol or mock client
    kwargs = {
        "symbol": symbol,
        "start_date": start_date,
        "end_date": end_date,
    }
    if "interval" in params or any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values()) or not params:
        kwargs["interval"] = interval
    return method(**kwargs)
