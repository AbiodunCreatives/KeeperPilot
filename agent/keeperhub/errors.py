"""Domain errors for the KeeperHub execution-layer client."""


class KeeperHubError(Exception):
    """Base error for all KeeperHub client failures."""


class KeeperHubAuthenticationError(KeeperHubError):
    """The API key was rejected (HTTP 401)."""


class KeeperHubNotFoundError(KeeperHubError):
    """The requested workflow, execution, or action does not exist (HTTP 404)."""


class KeeperHubUnavailableError(KeeperHubError):
    """Transient transport failure that did not recover after retries."""


class KeeperHubExecutionError(KeeperHubError):
    """KeeperHub rejected the request for a deterministic reason (tool error)."""


class MarketDataUnavailableError(KeeperHubError):
    """Yield market data could not be fetched from the market source."""
