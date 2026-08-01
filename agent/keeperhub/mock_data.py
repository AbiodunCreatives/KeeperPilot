"""Deterministic mock yield-market data for local development and tests.

Keyed by chain -> asset -> list of opportunities. In real mode this data comes
from KeeperHub (Task 7); the mock keeps the decision engine testable offline.
"""

MOCK_MARKET: dict[str, dict[str, list[dict[str, object]]]] = {
    "11155111": {
        "USDC": [
            {"protocol": "aave-v3", "apy": 4.8, "risk": "low", "estimated_gas": 1.2},
            {"protocol": "compound-v3", "apy": 4.2, "risk": "low", "estimated_gas": 1.0},
            {"protocol": "morpho", "apy": 6.1, "risk": "medium", "estimated_gas": 1.5},
            {"protocol": "fluid", "apy": 8.4, "risk": "medium", "estimated_gas": 2.2},
            {"protocol": "yield-farm-9000", "apy": 34.0, "risk": "high", "estimated_gas": 3.0},
        ],
        "USDT": [
            {"protocol": "aave-v3", "apy": 4.6, "risk": "low", "estimated_gas": 1.2},
            {"protocol": "morpho", "apy": 6.0, "risk": "medium", "estimated_gas": 1.4},
            {"protocol": "fluid", "apy": 8.1, "risk": "medium", "estimated_gas": 2.1},
        ],
        "DAI": [
            {"protocol": "aave-v3", "apy": 4.5, "risk": "low", "estimated_gas": 1.2},
            {"protocol": "compound-v3", "apy": 4.0, "risk": "low", "estimated_gas": 1.0},
            {"protocol": "morpho", "apy": 5.9, "risk": "medium", "estimated_gas": 1.5},
        ],
        "WETH": [
            {"protocol": "aave-v3", "apy": 2.8, "risk": "low", "estimated_gas": 1.8},
            {"protocol": "morpho", "apy": 4.5, "risk": "medium", "estimated_gas": 2.0},
            {"protocol": "fluid", "apy": 6.9, "risk": "high", "estimated_gas": 2.6},
        ],
    },
    "84532": {
        "USDC": [
            {"protocol": "aave-v3", "apy": 5.0, "risk": "low", "estimated_gas": 1.1},
            {"protocol": "morpho", "apy": 6.5, "risk": "medium", "estimated_gas": 1.4},
            {"protocol": "fluid", "apy": 8.8, "risk": "medium", "estimated_gas": 2.0},
        ],
        "USDT": [
            {"protocol": "aave-v3", "apy": 4.9, "risk": "low", "estimated_gas": 1.1},
            {"protocol": "morpho", "apy": 6.3, "risk": "medium", "estimated_gas": 1.4},
        ],
    },
}
