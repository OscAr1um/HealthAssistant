"""Abstract base class for notifiers."""

from abc import ABC, abstractmethod


class Notifier(ABC):
    """Abstract base class for sending notifications."""

    @abstractmethod
    def send(self, message: str) -> bool:
        """
        Send a notification message.

        Args:
            message: The message to send

        Returns:
            True if the message was sent successfully, False otherwise

        Raises:
            Exception: If sending fails critically
        """
        pass
