"""Main application entry point for Health Assistant."""

import argparse
import logging
import signal
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Dict, Optional

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from .analyzers.azure_openai import AzureOpenAIAnalyzer
from .config import Config, UserConfig
from .fetchers.oura import OuraFetcher
from .notifiers.telegram import TelegramNotifier
from .utils.logger import setup_logger


class UserHealthPipeline:
    """Health monitoring pipeline for a single user."""

    def __init__(
        self,
        user_config: UserConfig,
        analyzer: AzureOpenAIAnalyzer,
        logger: logging.Logger,
    ):
        """
        Initialize user-specific health pipeline.

        Args:
            user_config: User-specific configuration
            analyzer: Shared Azure OpenAI analyzer instance
            logger: Logger instance
        """
        self.user_config = user_config
        self.analyzer = analyzer
        self.logger = logger

        # Initialize user-specific components
        self.fetcher = OuraFetcher(
            access_token=user_config.oura["access_token"],
            user_id=user_config.oura.get("user_id"),
        )

        self.notifier = TelegramNotifier(
            bot_token=user_config.telegram["bot_token"],
            chat_id=user_config.telegram["chat_id"],
        )

    def run_health_check(self, target_date: Optional[date] = None) -> None:
        """
        Run health check for this user.

        Args:
            target_date: Date to fetch data for (defaults to yesterday)
        """
        user_id = self.user_config.user_id
        user_name = self.user_config.name

        self.logger.info(f"[{user_id}] Starting health check for user: {user_name}")

        try:
            # Calculate target date if not provided
            if target_date is None:
                target_date = date.today() - timedelta(days=1)

            self.logger.info(f"[{user_id}] Target date: {target_date}")

            # Step 1: Fetch health data
            self.logger.info(f"[{user_id}] Step 1/3: Fetching health data from Oura Ring...")
            health_data = self.fetcher.fetch_daily_data(target_date)
            self.logger.info(f"[{user_id}] ✓ Health data fetched successfully")

            # Debug: log what data was fetched
            data_summary = {
                "date": health_data.get("date"),
                "has_sleep": bool(health_data.get("sleep")),
                "has_activity": bool(health_data.get("activity")),
                "has_readiness": bool(health_data.get("readiness")),
                "has_heart_rate": bool(health_data.get("heart_rate")),
            }
            self.logger.debug(f"[{user_id}] Fetched data summary: {data_summary}")

            # Step 2: Analyze data with Azure OpenAI
            self.logger.info(f"[{user_id}] Step 2/3: Analyzing health data with Azure OpenAI...")
            analysis = self.analyzer.analyze(health_data)
            self.logger.info(f"[{user_id}] ✓ Analysis completed successfully")
            self.logger.debug(
                f"[{user_id}] Analysis length: {len(analysis) if analysis else 0} characters"
            )

            # Step 3: Send via Telegram
            self.logger.info(f"[{user_id}] Step 3/3: Sending summary via Telegram...")

            # Add header with date
            message = f"🏥 <b>Daily Health Summary</b>\n📅 {target_date.strftime('%A, %B %d, %Y')}\n\n{analysis}"

            success = self.notifier.send(message)

            if success:
                self.logger.info(f"[{user_id}] ✓ Summary sent successfully via Telegram")
                self.logger.info(f"[{user_id}] Health check completed successfully")
            else:
                self.logger.error(f"[{user_id}] ✗ Failed to send summary via Telegram")
                self.logger.error(f"[{user_id}] Health check completed with errors")

        except Exception as e:
            self.logger.error(f"[{user_id}] Health check failed: {e}", exc_info=True)

            # Try to send error notification
            try:
                error_message = (
                    f"⚠️ <b>Health Assistant Error</b>\n\n"
                    f"Failed to generate daily health summary for {user_name}.\n\n"
                    f"Error: {str(e)}\n\n"
                    f"Please check the logs for details."
                )
                self.notifier.send(error_message)
            except Exception as notify_error:
                self.logger.error(
                    f"[{user_id}] Failed to send error notification: {notify_error}"
                )
            raise  # Re-raise for tracking in daily_health_check



class HealthAssistant:
    """Main application class for Health Assistant with multi-user support."""

    def __init__(self, config_path: str | Path | None = None):
        """
        Initialize Health Assistant.

        Args:
            config_path: Path to configuration file
        """
        # Load configuration
        self.config = Config(config_path)

        # Setup logging
        log_config = self.config.logging
        self.logger = setup_logger(
            name="health_assistant",
            log_level=log_config.get("level", "INFO"),
            log_file=log_config.get("log_file"),
        )

        self.logger.info("=" * 80)
        self.logger.info("Health Assistant Starting (Multi-User Support)")
        self.logger.info("=" * 80)

        # Initialize shared Azure OpenAI analyzer
        self.logger.info("Initializing shared Azure OpenAI analyzer...")
        azure_config = self.config.azure
        self.analyzer = AzureOpenAIAnalyzer(
            endpoint=azure_config["endpoint"],
            api_key=azure_config["api_key"],
            deployment_name=azure_config["deployment_name"],
            api_version=azure_config.get("api_version", "2024-02-01"),
            model=azure_config.get("model", "gpt-4"),
            temperature=azure_config.get("temperature", 0.7),
            max_tokens=azure_config.get("max_tokens", 1500),
        )
        self.logger.info("✓ Azure OpenAI analyzer initialized")

        # Initialize user pipelines
        self.user_pipelines: Dict[str, UserHealthPipeline] = {}
        self._initialize_user_pipelines()

        # Setup scheduler
        self.scheduler = BlockingScheduler()
        self._setup_scheduler()

        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _initialize_user_pipelines(self) -> None:
        """Initialize health pipelines for all enabled users."""
        enabled_users = self.config.enabled_users

        if not enabled_users:
            self.logger.warning("No enabled users found in configuration")
            return

        self.logger.info(f"Initializing pipelines for {len(enabled_users)} enabled users...")

        for user_config in enabled_users:
            try:
                pipeline = UserHealthPipeline(
                    user_config=user_config,
                    analyzer=self.analyzer,
                    logger=self.logger,
                )

                self.user_pipelines[user_config.user_id] = pipeline
                self.logger.info(
                    f"✓ Initialized pipeline for user: {user_config.name} ({user_config.user_id})"
                )

            except Exception as e:
                self.logger.error(
                    f"Failed to initialize pipeline for user {user_config.user_id}: {e}",
                    exc_info=True,
                )
                # Continue with other users even if one fails

        if not self.user_pipelines:
            raise RuntimeError("Failed to initialize any user pipelines")

        self.logger.info(f"Successfully initialized {len(self.user_pipelines)} user pipelines")


    def _setup_scheduler(self) -> None:
        """Setup APScheduler with configured time."""
        scheduler_config = self.config.scheduler

        hour = scheduler_config["hour"]
        minute = scheduler_config["minute"]
        timezone = scheduler_config.get("timezone", "UTC")

        # Create cron trigger for daily execution
        trigger = CronTrigger(
            hour=hour,
            minute=minute,
            timezone=timezone,
        )

        self.scheduler.add_job(
            func=self.daily_health_check,
            trigger=trigger,
            id="daily_health_check",
            name="Daily Health Check (All Users)",
            replace_existing=True,
        )

        self.logger.info(
            f"Scheduler configured: Daily execution at {hour:02d}:{minute:02d} {timezone} "
            f"for {len(self.user_pipelines)} users"
        )

    def daily_health_check(self) -> None:
        """
        Main function to fetch, analyze, and send daily health summary for all users.
        This runs daily at the scheduled time.
        """
        self.logger.info("=" * 80)
        self.logger.info("Starting daily health check for all users")
        self.logger.info("=" * 80)

        if not self.user_pipelines:
            self.logger.error("No user pipelines available")
            return

        # Track statistics
        total_users = len(self.user_pipelines)
        successful = 0
        failed = 0

        # Process each user independently
        for user_id, pipeline in self.user_pipelines.items():
            try:
                pipeline.run_health_check()
                successful += 1
            except Exception as e:
                # This should rarely happen since UserHealthPipeline handles its own exceptions
                self.logger.error(
                    f"Unexpected error processing user {user_id}: {e}",
                    exc_info=True,
                )
                failed += 1

        # Log summary
        self.logger.info("=" * 80)
        self.logger.info(
            f"Daily health check completed: {successful}/{total_users} successful, {failed} failed"
        )
        self.logger.info("=" * 80)


    def run_now(self) -> None:
        """Run health check immediately (for testing)."""
        self.logger.info("Running health check immediately (test mode)")
        self.daily_health_check()

    def run(self) -> None:
        """Start the scheduler and run indefinitely."""
        self.logger.info("Starting scheduler...")
        self.logger.info("Press Ctrl+C to stop")

        try:
            self.scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            self.logger.info("Shutdown requested")
            self._shutdown()

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        self.logger.info(f"Received signal {signum}, initiating shutdown...")
        self._shutdown()

    def _shutdown(self) -> None:
        """Graceful shutdown."""
        self.logger.info("Shutting down Health Assistant...")

        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)

        self.logger.info("=" * 80)
        self.logger.info("Health Assistant Stopped")
        self.logger.info("=" * 80)

        sys.exit(0)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Health Assistant - Daily Health Summary Service",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m src.main                 Run as scheduled service
  python -m src.main --now           Run health check immediately
  python -m src.main --config /path/to/config.yaml
        """,
    )

    parser.add_argument(
        "--now",
        action="store_true",
        help="Run health check immediately instead of starting scheduler",
    )

    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to configuration file (default: config.yaml in project root)",
    )

    args = parser.parse_args()

    try:
        # Initialize application
        app = HealthAssistant(config_path=args.config)

        if args.now:
            # Run immediately for testing
            app.run_now()
        else:
            # Run as scheduled service
            app.run()

    except FileNotFoundError as e:
        print(f"Error: {e}")
        print("\nPlease create config.yaml based on config.yaml.example")
        sys.exit(1)

    except ValueError as e:
        print(f"Configuration error: {e}")
        print("\nPlease check your config.yaml file")
        sys.exit(1)

    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
