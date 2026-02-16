"""Oura Ring API data fetcher."""

import time
from datetime import date, timedelta
from typing import Any, Dict, Optional

import requests

from ..fetchers.base import DataFetcher
from ..utils.logger import get_logger
from ..utils.rate_limiter import RateLimiter


class OuraFetcher(DataFetcher):
    """Fetcher for Oura Ring health data via API v2."""

    BASE_URL = "https://api.ouraring.com/v2/usercollection"

    def __init__(
        self,
        access_token: str,
        user_id: Optional[str] = None,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ):
        """
        Initialize Oura Ring API client.

        Args:
            access_token: Oura Personal Access Token
            user_id: Optional Oura user ID (not typically needed for personal tokens)
            max_retries: Maximum number of retry attempts for failed requests
            retry_delay: Initial delay between retries in seconds (uses exponential backoff)
        """
        self.access_token = access_token
        self.user_id = user_id
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.rate_limiter = RateLimiter(max_requests=100, time_window=60)  # 100 req/min
        self.logger = get_logger(__name__)

        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json",
            }
        )

    def fetch_daily_data(self, target_date: date) -> Dict[str, Any]:
        """
        Fetch comprehensive health data for a specific date.

        Args:
            target_date: The date to fetch data for

        Returns:
            Dictionary containing all health metrics for the date

        Raises:
            Exception: If data fetching fails after retries
        """
        self.logger.info(f"Fetching Oura data for date: {target_date}")

        # Format date for API (ISO 8601)
        date_str = target_date.isoformat()

        # Fetch all data types
        data = {
            "date": date_str,
            "sleep": self._fetch_sleep(date_str),
            "activity": self._fetch_activity(date_str),
            "readiness": self._fetch_readiness(date_str),
            "heart_rate": self._fetch_heart_rate(date_str),
        }

        self.logger.info(f"Successfully fetched Oura data for {target_date}")
        return data

    def _fetch_sleep(self, date_str: str) -> Dict[str, Any]:
        """Fetch sleep data for a specific date."""
        try:
            endpoint = f"{self.BASE_URL}/daily_sleep"
            params = {"start_date": date_str, "end_date": date_str}
            response = self._make_request(endpoint, params)

            if response and "data" in response and len(response["data"]) > 0:
                return response["data"][0]
            return {}
        except Exception as e:
            self.logger.warning(f"Failed to fetch sleep data: {e}")
            return {}

    def _fetch_activity(self, date_str: str) -> Dict[str, Any]:
        """Fetch activity data for a specific date."""
        try:
            endpoint = f"{self.BASE_URL}/daily_activity"
            params = {"start_date": date_str, "end_date": date_str}
            response = self._make_request(endpoint, params)

            if response and "data" in response and len(response["data"]) > 0:
                return response["data"][0]
            return {}
        except Exception as e:
            self.logger.warning(f"Failed to fetch activity data: {e}")
            return {}

    def _fetch_readiness(self, date_str: str) -> Dict[str, Any]:
        """Fetch readiness data for a specific date."""
        try:
            endpoint = f"{self.BASE_URL}/daily_readiness"
            params = {"start_date": date_str, "end_date": date_str}
            response = self._make_request(endpoint, params)

            if response and "data" in response and len(response["data"]) > 0:
                return response["data"][0]
            return {}
        except Exception as e:
            self.logger.warning(f"Failed to fetch readiness data: {e}")
            return {}

    def _fetch_heart_rate(self, date_str: str) -> Dict[str, Any]:
        """Fetch heart rate data for a specific date."""
        try:
            endpoint = f"{self.BASE_URL}/heartrate"
            params = {"start_date": date_str, "end_date": date_str}
            response = self._make_request(endpoint, params)

            if response and "data" in response:
                # Heart rate returns multiple datapoints, so we aggregate
                return self._aggregate_heart_rate(response["data"])
            return {}
        except Exception as e:
            self.logger.warning(f"Failed to fetch heart rate data: {e}")
            return {}

    def _aggregate_heart_rate(self, hr_data: list) -> Dict[str, Any]:
        """
        Aggregate heart rate data points into summary statistics.

        Args:
            hr_data: List of heart rate data points

        Returns:
            Dictionary with aggregated heart rate statistics
        """
        if not hr_data:
            return {}

        heart_rates = [point.get("bpm") for point in hr_data if point.get("bpm")]

        if not heart_rates:
            return {}

        return {
            "min_hr": min(heart_rates),
            "max_hr": max(heart_rates),
            "avg_hr": sum(heart_rates) / len(heart_rates),
            "data_points": len(heart_rates),
        }

    def _make_request(
        self, endpoint: str, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Make HTTP request to Oura API with rate limiting and retry logic.

        Args:
            endpoint: API endpoint URL
            params: Query parameters

        Returns:
            JSON response as dictionary

        Raises:
            Exception: If request fails after all retries
        """
        for attempt in range(self.max_retries):
            try:
                # Wait for rate limiter
                self.rate_limiter.acquire()

                response = self.session.get(endpoint, params=params, timeout=30)

                # Handle rate limiting
                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 60))
                    self.logger.warning(
                        f"Rate limited. Waiting {retry_after} seconds before retry."
                    )
                    time.sleep(retry_after)
                    continue

                # Raise for other HTTP errors
                response.raise_for_status()

                return response.json()

            except requests.exceptions.RequestException as e:
                self.logger.warning(
                    f"Request failed (attempt {attempt + 1}/{self.max_retries}): {e}"
                )

                if attempt < self.max_retries - 1:
                    # Exponential backoff
                    delay = self.retry_delay * (2**attempt)
                    self.logger.info(f"Retrying in {delay} seconds...")
                    time.sleep(delay)
                else:
                    # Final attempt failed
                    self.logger.error(f"All retry attempts failed for {endpoint}")
                    raise

        raise Exception(f"Failed to fetch data from {endpoint} after {self.max_retries} attempts")

    def __del__(self):
        """Cleanup session on deletion."""
        if hasattr(self, "session"):
            self.session.close()
