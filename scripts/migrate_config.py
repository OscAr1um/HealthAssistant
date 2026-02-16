#!/usr/bin/env python3
"""
Migrate legacy single-user config.yaml to multi-user format.

Usage:
    python scripts/migrate_config.py config.yaml
    python scripts/migrate_config.py --input old.yaml --output new.yaml
    python scripts/migrate_config.py --user-id my_user config.yaml
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

import yaml


def migrate_config(
    input_path: str, output_path: str = None, user_id: str = "default_user"
) -> None:
    """
    Migrate legacy config to multi-user format.

    Args:
        input_path: Path to input config file
        output_path: Path to output config file (default: overwrite with backup)
        user_id: User ID for the migrated user (default: "default_user")
    """
    input_file = Path(input_path)

    if not input_file.exists():
        print(f"❌ Error: Config file not found: {input_path}")
        sys.exit(1)

    # Load old config
    print(f"📖 Reading config from: {input_path}")
    with open(input_file, "r", encoding="utf-8") as f:
        old_config = yaml.safe_load(f)

    # Check if already in new format
    if "users" in old_config:
        print(f"✓ Config is already in multi-user format")
        print(f"   Found {len(old_config['users'])} users configured")
        return

    # Check if it's a legacy format
    if "oura" not in old_config or "telegram" not in old_config:
        print(
            f"❌ Error: Config file doesn't appear to be a valid Health Assistant config"
        )
        print(f"   Missing 'oura' or 'telegram' sections")
        sys.exit(1)

    print(f"🔄 Migrating legacy single-user config to multi-user format...")

    # Create new config structure
    new_config = {
        "azure": old_config.get("azure", {}),
        "scheduler": old_config.get("scheduler", {}),
        "logging": old_config.get("logging", {}),
        "users": [
            {
                "id": user_id,
                "name": user_id.replace("_", " ").title(),  # "default_user" -> "Default User"
                "enabled": True,
                "oura": old_config.get("oura", {}),
                "telegram": old_config.get("telegram", {}),
            }
        ],
    }

    # Determine output path
    if output_path is None:
        # Create backup of original
        backup_path = (
            f"{input_path}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )
        input_file.rename(backup_path)
        print(f"✓ Created backup: {backup_path}")
        output_path = input_path

    # Write new config
    output_file = Path(output_path)
    with open(output_file, "w", encoding="utf-8") as f:
        yaml.dump(new_config, f, default_flow_style=False, sort_keys=False, indent=2)

    print(f"✓ Migrated config saved to: {output_path}")
    print(f"\n📋 Migration Summary:")
    print(f"   • Created user: {user_id}")
    print(f"   • User name: {new_config['users'][0]['name']}")
    print(f"   • Oura token: {'***' + old_config['oura']['access_token'][-8:]}")
    print(f"   • Telegram chat ID: {old_config['telegram']['chat_id']}")
    print(f"\n📝 Next Steps:")
    print(f"   1. Review the migrated config at: {output_path}")
    print(f"   2. To add more users, see: config.yaml.example.multi")
    print(f"   3. Test with: python -m src.main --now")
    print(f"   4. If satisfied, run in production: python -m src.main")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Migrate Health Assistant config.yaml to multi-user format",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Migrate config.yaml (creates backup)
  python scripts/migrate_config.py config.yaml

  # Migrate to a different file
  python scripts/migrate_config.py --input old.yaml --output new.yaml

  # Migrate with custom user ID
  python scripts/migrate_config.py --user-id alice config.yaml
        """,
    )

    parser.add_argument(
        "input", nargs="?", default="config.yaml", help="Input config file (default: config.yaml)"
    )

    parser.add_argument(
        "--output",
        "-o",
        help="Output file (default: overwrite input with backup)",
    )

    parser.add_argument(
        "--user-id",
        default="default_user",
        help="User ID for migrated user (default: default_user)",
    )

    args = parser.parse_args()

    try:
        migrate_config(args.input, args.output, args.user_id)
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
