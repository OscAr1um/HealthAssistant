"""Abstract base class for data analyzers."""

from abc import ABC, abstractmethod
from typing import Any, Dict


class DataAnalyzer(ABC):
    """Abstract base class for analyzing health data."""

    @abstractmethod
    def analyze(self, data: Dict[str, Any]) -> str:
        """
        Analyze health data and return a summary.

        Args:
            data: Dictionary containing health data to analyze

        Returns:
            String containing the analysis summary

        Raises:
            Exception: If analysis fails
        """
        pass
