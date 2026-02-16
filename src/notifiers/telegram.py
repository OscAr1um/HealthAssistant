"""Telegram bot notifier."""

import asyncio
import time
from typing import List

from telegram import Bot
from telegram.constants import ParseMode
from telegram.error import TelegramError

from ..notifiers.base import Notifier
from ..utils.logger import get_logger


class TelegramNotifier(Notifier):
    """Notifier that sends messages via Telegram bot."""

    MAX_MESSAGE_LENGTH = 4096  # Telegram's message length limit

    def __init__(
        self,
        bot_token: str,
        chat_id: str,
        max_retries: int = 3,
        retry_delay: float = 2.0,
    ):
        """
        Initialize Telegram notifier.

        Args:
            bot_token: Telegram bot token from @BotFather
            chat_id: Telegram chat ID to send messages to
            max_retries: Maximum number of retry attempts
            retry_delay: Delay between retries in seconds
        """
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.logger = get_logger(__name__)

        # Initialize bot
        self.bot = Bot(token=bot_token)

    def send(self, message: str) -> bool:
        """
        Send a message via Telegram.

        Args:
            message: Message text to send (supports HTML formatting)

        Returns:
            True if message was sent successfully, False otherwise
        """
        self.logger.info("Sending message via Telegram")

        try:
            # Split message if it exceeds Telegram's limit
            if len(message) > self.MAX_MESSAGE_LENGTH:
                self.logger.warning(
                    f"Message length ({len(message)}) exceeds Telegram limit, splitting..."
                )
                messages = self._split_long_message(message)
            else:
                messages = [message]

            # Send all message parts
            for i, msg in enumerate(messages):
                success = self._send_with_retry(msg)
                if not success:
                    self.logger.error(f"Failed to send message part {i + 1}/{len(messages)}")
                    return False

                # Small delay between messages to avoid rate limiting
                if i < len(messages) - 1:
                    time.sleep(0.5)

            self.logger.info("Successfully sent all message parts via Telegram")
            return True

        except Exception as e:
            self.logger.error(f"Failed to send Telegram message: {e}")
            return False

    def _send_with_retry(self, message: str) -> bool:
        """
        Send a single message with retry logic.

        Args:
            message: Message text to send

        Returns:
            True if successful, False otherwise
        """
        for attempt in range(self.max_retries):
            try:
                # Try with HTML parsing (more reliable than Markdown for LLM output)
                asyncio.run(
                    self.bot.send_message(
                        chat_id=self.chat_id,
                        text=message,
                        parse_mode=ParseMode.HTML,
                    )
                )
                return True

            except TelegramError as e:
                # If Markdown parsing fails, try without formatting
                if "can't parse" in str(e).lower():
                    self.logger.warning("Markdown parsing failed, sending as plain text")
                    try:
                        asyncio.run(
                            self.bot.send_message(
                                chat_id=self.chat_id,
                                text=message,
                            )
                        )
                        return True
                    except TelegramError as e2:
                        self.logger.error(f"Plain text send also failed: {e2}")

                self.logger.warning(
                    f"Telegram send attempt {attempt + 1}/{self.max_retries} failed: {e}"
                )

                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (2**attempt)
                    self.logger.info(f"Retrying in {delay} seconds...")
                    time.sleep(delay)

            except Exception as e:
                self.logger.error(f"Unexpected error sending Telegram message: {e}")
                return False

        return False

    def _split_long_message(self, message: str) -> List[str]:
        """
        Split a long message into multiple parts.

        Args:
            message: Long message to split

        Returns:
            List of message parts, each within Telegram's limit
        """
        messages = []
        current_message = ""

        # Split by lines to maintain formatting
        lines = message.split("\n")

        for line in lines:
            # If adding this line would exceed the limit
            if len(current_message) + len(line) + 1 > self.MAX_MESSAGE_LENGTH:
                if current_message:
                    messages.append(current_message)
                    current_message = ""

                # If a single line is too long, split it by words
                if len(line) > self.MAX_MESSAGE_LENGTH:
                    words = line.split()
                    for word in words:
                        if len(current_message) + len(word) + 1 > self.MAX_MESSAGE_LENGTH:
                            messages.append(current_message)
                            current_message = word
                        else:
                            current_message += " " + word if current_message else word
                else:
                    current_message = line
            else:
                current_message += "\n" + line if current_message else line

        # Add remaining message
        if current_message:
            messages.append(current_message)

        self.logger.info(f"Split message into {len(messages)} parts")
        return messages
