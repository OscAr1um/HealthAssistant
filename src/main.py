"""Main application entry point for Health Assistant."""

import argparse
import signal
import sys
from datetime import date, timedelta
from pathlib import Path

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from .analyzers.azure_openai import AzureOpenAIAnalyzer
from .config import Config
from .fetchers.oura import OuraFetcher
from .notifiers.telegram import TelegramNotifier
from .utils.logger import setup_logger


class HealthAssistant:
    """Main application class for Health Assistant."""

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
        self.logger.info("Health Assistant Starting")
        self.logger.info("=" * 80)

        # Initialize components
        self._initialize_components()

        # Setup scheduler
        self.scheduler = BlockingScheduler()
        self._setup_scheduler()

        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _initialize_components(self) -> None:
        """Initialize fetcher, analyzer, and notifier components."""
        self.logger.info("Initializing components...")

        # Initialize Oura Ring fetcher
        oura_config = self.config.oura
        self.fetcher = OuraFetcher(
            access_token=oura_config["access_token"],
            user_id=oura_config.get("user_id"),
        )
        self.logger.info("✓ Oura Ring fetcher initialized")

        # Initialize Azure OpenAI analyzer
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

        # Initialize Telegram notifier
        telegram_config = self.config.telegram
        self.notifier = TelegramNotifier(
            bot_token=telegram_config["bot_token"],
            chat_id=telegram_config["chat_id"],
        )
        self.logger.info("✓ Telegram notifier initialized")

        self.logger.info("All components initialized successfully")

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
            name="Daily Health Check",
            replace_existing=True,
        )

        self.logger.info(
            f"Scheduler configured: Daily execution at {hour:02d}:{minute:02d} {timezone}"
        )

    def daily_health_check(self) -> None:
        """
        Main function to fetch, analyze, and send daily health summary.
        This runs daily at the scheduled time.
        """
        self.logger.info("=" * 80)
        self.logger.info("Starting daily health check")
        self.logger.info("=" * 80)

        try:
            # Calculate target date (yesterday, as Oura data is finalized the next day)
            target_date = date.today() - timedelta(days=1)
            self.logger.info(f"Target date: {target_date}")

            # Step 1: Fetch health data
            self.logger.info("Step 1/3: Fetching health data from Oura Ring...")
            health_data = self.fetcher.fetch_daily_data(target_date)
            self.logger.info("✓ Health data fetched successfully")

            # Debug: log what data was fetched
            data_summary = {
                "date": health_data.get("date"),
                "has_sleep": bool(health_data.get("sleep")),
                "has_activity": bool(health_data.get("activity")),
                "has_readiness": bool(health_data.get("readiness")),
                "has_heart_rate": bool(health_data.get("heart_rate")),
            }
            self.logger.debug(f"Fetched data summary: {data_summary}")

            # Step 2: Analyze data with Azure OpenAI
            self.logger.info("Step 2/3: Analyzing health data with Azure OpenAI...")
            analysis = self.analyzer.analyze(health_data)
            self.logger.info("✓ Analysis completed successfully")
            self.logger.debug(f"Analysis length: {len(analysis) if analysis else 0} characters")

            # Step 3: Send via Telegram
            self.logger.info("Step 3/3: Sending summary via Telegram...")

            # Add header with date
            message = f"🏥 <b>Daily Health Summary</b>\n📅 {target_date.strftime('%A, %B %d, %Y')}\n\n{analysis}"

            success = self.notifier.send(message)

            if success:
                self.logger.info("✓ Summary sent successfully via Telegram")
                self.logger.info("=" * 80)
                self.logger.info("Daily health check completed successfully")
                self.logger.info("=" * 80)
            else:
                self.logger.error("✗ Failed to send summary via Telegram")
                self.logger.info("=" * 80)
                self.logger.error("Daily health check completed with errors")
                self.logger.info("=" * 80)

        except Exception as e:
            self.logger.error(f"Daily health check failed: {e}", exc_info=True)
            self.logger.info("=" * 80)
            self.logger.error("Daily health check failed")
            self.logger.info("=" * 80)

            # Try to send error notification
            try:
                error_message = (
                    f"⚠️ <b>Health Assistant Error</b>\n\n"
                    f"Failed to generate daily health summary.\n\n"
                    f"Error: {str(e)}\n\n"
                    f"Please check the logs for details."
                )
                self.notifier.send(error_message)
            except Exception as notify_error:
                self.logger.error(f"Failed to send error notification: {notify_error}")

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
