"""FDB (First DataBank) adapter interface.

The concrete implementation is STUBBED pending receipt of the FDB integration
specification. The interface is defined here so calling code can be written
against it now.

When the FDB spec arrives:
1. Implement _FDBConcreteAdapter._parse_feed()
2. Implement _FDBConcreteAdapter._fetch_feed()
3. Remove the NotImplementedError markers
4. Document the FDB-specific field mapping in README.md
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger(__name__)


class FDBAdapter(ABC):
    """Abstract interface for First DataBank data feed integration."""

    @abstractmethod
    def fetch_feed(self) -> bytes:  # pragma: no cover
        """Download the latest FDB data feed. Returns raw bytes."""

    @abstractmethod
    def parse_feed(self, raw: bytes) -> list[dict[str, Any]]:  # pragma: no cover
        """Parse raw FDB feed into normalized drug product dicts."""

    @abstractmethod
    def parse_pricing(self, raw: bytes) -> list[dict[str, Any]]:  # pragma: no cover
        """Parse FDB pricing feed (AWP/WAC) into pricing dicts."""

    @abstractmethod
    def parse_interactions(self, raw: bytes) -> list[dict[str, Any]]:  # pragma: no cover
        """Parse FDB drug interaction data."""

    @abstractmethod
    def parse_dosing(self, raw: bytes) -> list[dict[str, Any]]:  # pragma: no cover
        """Parse FDB dosing limits data."""


class FDBAdapterStub(FDBAdapter):
    """Stubbed FDB adapter — raises NotImplementedError until spec received.

    This stub exists so the DI container and refresh pipeline can reference
    FDBAdapter without a live FDB contract. Replace with a real adapter once
    the FDB integration spec is delivered.
    """

    def fetch_feed(self) -> bytes:
        raise NotImplementedError("FDB spec TBD")

    def parse_feed(self, raw: bytes) -> list[dict[str, Any]]:
        raise NotImplementedError("FDB spec TBD")

    def parse_pricing(self, raw: bytes) -> list[dict[str, Any]]:
        raise NotImplementedError("FDB spec TBD")

    def parse_interactions(self, raw: bytes) -> list[dict[str, Any]]:
        raise NotImplementedError("FDB spec TBD")

    def parse_dosing(self, raw: bytes) -> list[dict[str, Any]]:
        raise NotImplementedError("FDB spec TBD")
