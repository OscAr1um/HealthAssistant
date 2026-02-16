"""Abstract base class for data fetchers."""

from abc import ABC, abstractmethod
from datetime import date
from typing import Any, Dict


class DataFetcher(ABC):
    """Abstract base class for fetching health data from various sources."""

    @abstractmethod
    def fetch_daily_data(self, target_date: date) -> Dict[str, Any]:
        """
        Fetch health data for a specific date.

        Args:
            target_date: The date to fetch data for

        Returns:
            Dictionary containing health data for the specified date

        Raises:
            Exception: If data fetching fails
        """
        pass
