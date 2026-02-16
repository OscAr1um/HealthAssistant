"""Configuration loader for Health Assistant."""

import os
from pathlib import Path
from typing import Any, Dict

import yaml


class Config:
    """Configuration manager for Health Assistant."""

    def __init__(self, config_path: str | Path | None = None):
        """
        Initialize configuration.

        Args:
            config_path: Path to config.yaml file. If None, looks for config.yaml in project root.
        """
        if config_path is None:
            # Default to config.yaml in project root
            project_root = Path(__file__).parent.parent
            config_path = project_root / "config.yaml"
        else:
            config_path = Path(config_path)

        if not config_path.exists():
            raise FileNotFoundError(
                f"Configuration file not found: {config_path}\n"
                f"Please create config.yaml based on config.yaml.example"
            )

        with open(config_path, "r", encoding="utf-8") as f:
            self._config: Dict[str, Any] = yaml.safe_load(f)

        self._validate()

    def _validate(self) -> None:
        """Validate that all required configuration fields are present."""
        # Validate Oura configuration
        if "oura" not in self._config:
            raise ValueError("Missing 'oura' section in configuration")
        if not self._config["oura"].get("access_token"):
            raise ValueError("Missing 'oura.access_token' in configuration")

        # Validate Azure configuration
        if "azure" not in self._config:
            raise ValueError("Missing 'azure' section in configuration")
        azure_fields = ["endpoint", "api_key", "deployment_name"]
        for field in azure_fields:
            if not self._config["azure"].get(field):
                raise ValueError(f"Missing 'azure.{field}' in configuration")

        # Validate Telegram configuration
        if "telegram" not in self._config:
            raise ValueError("Missing 'telegram' section in configuration")
        telegram_fields = ["bot_token", "chat_id"]
        for field in telegram_fields:
            if not self._config["telegram"].get(field):
                raise ValueError(f"Missing 'telegram.{field}' in configuration")

        # Validate scheduler configuration
        if "scheduler" not in self._config:
            raise ValueError("Missing 'scheduler' section in configuration")
        if "hour" not in self._config["scheduler"]:
            raise ValueError("Missing 'scheduler.hour' in configuration")
        if "minute" not in self._config["scheduler"]:
            raise ValueError("Missing 'scheduler.minute' in configuration")

    @property
    def oura(self) -> Dict[str, Any]:
        """Get Oura Ring configuration."""
        return self._config["oura"]

    @property
    def azure(self) -> Dict[str, Any]:
        """Get Azure OpenAI configuration."""
        return self._config["azure"]

    @property
    def telegram(self) -> Dict[str, Any]:
        """Get Telegram configuration."""
        return self._config["telegram"]

    @property
    def scheduler(self) -> Dict[str, Any]:
        """Get scheduler configuration."""
        return self._config["scheduler"]

    @property
    def logging(self) -> Dict[str, Any]:
        """Get logging configuration."""
        return self._config.get("logging", {"level": "INFO", "log_file": "health_assistant.log"})

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value by key.

        Args:
            key: Configuration key (supports dot notation, e.g., 'azure.endpoint')
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        keys = key.split(".")
        value = self._config
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value
