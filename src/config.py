"""Configuration loader for Health Assistant."""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


logger = logging.getLogger(__name__)


class UserConfig:
    """Configuration for a single user."""

    def __init__(self, user_data: Dict[str, Any]):
        """
        Initialize user configuration.

        Args:
            user_data: Dictionary containing user-specific config
        """
        self._data = user_data
        self._validate()

    def _validate(self) -> None:
        """Validate required user fields."""
        required_fields = [
            ("id", "User ID"),
            ("oura.access_token", "Oura access token"),
            ("telegram.bot_token", "Telegram bot token"),
            ("telegram.chat_id", "Telegram chat ID"),
        ]

        for field, display_name in required_fields:
            if not self.get(field):
                raise ValueError(f"Missing required user field: {display_name} ({field})")

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get nested config value using dot notation.

        Args:
            key: Configuration key (supports dot notation, e.g., 'oura.access_token')
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        keys = key.split(".")
        value = self._data

        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return default
            else:
                return default

        return value

    @property
    def user_id(self) -> str:
        """Get user ID."""
        return self._data["id"]

    @property
    def name(self) -> str:
        """Get user name (defaults to user_id if not set)."""
        return self._data.get("name", self._data["id"])

    @property
    def enabled(self) -> bool:
        """Check if user is enabled."""
        return self._data.get("enabled", True)

    @property
    def oura(self) -> Dict[str, Any]:
        """Get Oura configuration."""
        return self._data.get("oura", {})

    @property
    def telegram(self) -> Dict[str, Any]:
        """Get Telegram configuration."""
        return self._data.get("telegram", {})


class Config:
    """Configuration manager for Health Assistant with multi-user support."""

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

        self._detect_and_migrate_legacy()
        self._validate()
        self._users = self._load_users()

    def _detect_and_migrate_legacy(self) -> None:
        """Detect and migrate legacy single-user config to multi-user format."""
        # Check if this is a legacy config (has top-level oura/telegram but no users array)
        if "oura" in self._config and "users" not in self._config:
            logger.warning(
                "Detected legacy single-user configuration. Automatically migrating to multi-user format..."
            )

            # Create a single user from legacy config
            legacy_user = {
                "id": "default_user",
                "name": "Default User",
                "oura": self._config.get("oura", {}),
                "telegram": self._config.get("telegram", {}),
                "enabled": True,
            }

            # Add users array
            self._config["users"] = [legacy_user]

            # Remove top-level oura/telegram (keep azure, scheduler, logging)
            self._config.pop("oura", None)
            self._config.pop("telegram", None)

            logger.info(
                "Legacy configuration migrated successfully. "
                "Consider updating config.yaml to new format for multi-user support."
            )

    def _validate(self) -> None:
        """Validate that all required configuration fields are present."""
        # Validate Azure configuration
        if "azure" not in self._config:
            raise ValueError("Missing 'azure' section in configuration")
        azure_fields = ["endpoint", "api_key", "deployment_name"]
        for field in azure_fields:
            if not self._config["azure"].get(field):
                raise ValueError(f"Missing 'azure.{field}' in configuration")

        # Validate scheduler configuration
        if "scheduler" not in self._config:
            raise ValueError("Missing 'scheduler' section in configuration")
        if "hour" not in self._config["scheduler"]:
            raise ValueError("Missing 'scheduler.hour' in configuration")
        if "minute" not in self._config["scheduler"]:
            raise ValueError("Missing 'scheduler.minute' in configuration")

        # Validate users array exists and is not empty
        if "users" not in self._config or not self._config["users"]:
            raise ValueError("Configuration must contain at least one user in 'users' array")

        if not isinstance(self._config["users"], list):
            raise ValueError("'users' must be an array/list")

    def _load_users(self) -> List[UserConfig]:
        """Load and validate all user configurations."""
        users = []
        user_ids_seen = set()

        for idx, user_data in enumerate(self._config.get("users", [])):
            try:
                user_config = UserConfig(user_data)

                # Check for duplicate user IDs
                if user_config.user_id in user_ids_seen:
                    raise ValueError(f"Duplicate user ID: {user_config.user_id}")

                user_ids_seen.add(user_config.user_id)
                users.append(user_config)

                logger.info(
                    f"Loaded user configuration: {user_config.name} ({user_config.user_id})"
                )

            except Exception as e:
                logger.error(f"Failed to load user configuration at index {idx}: {e}")
                raise ValueError(f"Invalid user configuration at index {idx}: {e}")

        return users

    @property
    def users(self) -> List[UserConfig]:
        """Get all user configurations."""
        return self._users

    @property
    def enabled_users(self) -> List[UserConfig]:
        """Get only enabled user configurations."""
        return [user for user in self._users if user.enabled]

    def get_user(self, user_id: str) -> Optional[UserConfig]:
        """
        Get specific user configuration by ID.

        Args:
            user_id: User ID to look up

        Returns:
            UserConfig if found, None otherwise
        """
        for user in self._users:
            if user.user_id == user_id:
                return user
        return None

    @property
    def oura(self) -> Dict[str, Any]:
        """
        Get Oura Ring configuration (legacy compatibility).

        Note: For multi-user support, use config.users instead.
        This property is maintained for backward compatibility.
        """
        # Return first user's oura config if available (legacy compatibility)
        if self._users:
            return self._users[0].oura
        return {}

    @property
    def telegram(self) -> Dict[str, Any]:
        """
        Get Telegram configuration (legacy compatibility).

        Note: For multi-user support, use config.users instead.
        This property is maintained for backward compatibility.
        """
        # Return first user's telegram config if available (legacy compatibility)
        if self._users:
            return self._users[0].telegram
        return {}


    @property
    def azure(self) -> Dict[str, Any]:
        """Get Azure OpenAI configuration (shared across all users)."""
        return self._config["azure"]

    @property
    def scheduler(self) -> Dict[str, Any]:
        """Get scheduler configuration (shared across all users)."""
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
