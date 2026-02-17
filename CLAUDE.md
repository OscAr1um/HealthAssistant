# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Health Assistant is a modular daily health monitoring system that fetches data from Oura Ring, analyzes it with Azure OpenAI, and sends personalized health summaries via Telegram. The system supports **multiple users** with a single deployment, where each user has their own Oura token and Telegram bot/chat. The system uses APScheduler to run daily at a configured time.

## Common Commands

### Running the Application

```bash
# Test run (immediate execution, fetches yesterday's data)
python -m src.main --now

# Production run (scheduled service)
python -m src.main

# With custom config file
python -m src.main --config /path/to/config.yaml
```

### Development Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Create configuration file (multi-user)
cp config.yaml.example.multi config.yaml
# Then edit config.yaml with your users' credentials
```

### Testing

Currently, there is no formal test suite. Tests directory exists but contains only `__init__.py`.

## Architecture

The codebase follows a **modular pipeline architecture** with multi-user support:

```
HealthAssistant
├── Shared: AzureOpenAIAnalyzer (stateless, used by all users)
└── Per-User: UserHealthPipeline[]
    ├── OuraFetcher (user's token)
    ├── TelegramNotifier (user's bot/chat)
    └── Runs independently with error isolation
```

### Multi-User Design

- **UserHealthPipeline**: Encapsulates each user's complete health monitoring flow
- **Shared Azure Analyzer**: All users share a single AzureOpenAIAnalyzer instance (cost-effective, stateless)
- **Per-User Components**: Each user gets their own OuraFetcher and TelegramNotifier instances
- **Error Isolation**: One user's failure doesn't affect others
- **Fresh Conversations**: Each user gets a new LLM conversation (no shared state)

### Core Components

1. **Fetchers** (`src/fetchers/`): Fetch health data from various sources
   - Base class: `DataFetcher` (abstract base with `fetch_daily_data()` method)
   - Implementation: `OuraFetcher` - fetches sleep, activity, readiness, and heart rate data from Oura Ring API v2

2. **Analyzers** (`src/analyzers/`): Process and analyze health data
   - Base class: `DataAnalyzer` (abstract base with `analyze()` method)
   - Implementation: `AzureOpenAIAnalyzer` - generates personalized health insights using Azure OpenAI

3. **Notifiers** (`src/notifiers/`): Send results to users
   - Base class: `Notifier` (abstract base with `send()` method)
   - Implementation: `TelegramNotifier` - sends messages via Telegram bot with HTML formatting

### Key Design Patterns

- **Abstract Base Classes**: All three main components (fetcher, analyzer, notifier) use ABC to enable easy extension
- **Dependency Injection**: Main application (`HealthAssistant` class) receives config path and initializes all components
- **Rate Limiting**: Custom token bucket rate limiter (`RateLimiter`) controls API request rates
- **Retry Logic**: Both `OuraFetcher` and `TelegramNotifier` implement exponential backoff retry logic
- **Scheduled Execution**: Uses APScheduler's `BlockingScheduler` with `CronTrigger` for daily execution

### Data Flow

1. `main.py` → `HealthAssistant` class initializes components from `config.yaml`
2. Shared `AzureOpenAIAnalyzer` initialized once for all users
3. `UserHealthPipeline` created for each enabled user with their own fetcher/notifier
4. Scheduler triggers `daily_health_check()` at configured time
5. For each user:
   - `OuraFetcher.fetch_daily_data()` fetches yesterday's data (Oura data is finalized the next day)
   - `AzureOpenAIAnalyzer.analyze()` sends structured prompt with health data to Azure OpenAI
   - `TelegramNotifier.send()` delivers the analysis as HTML-formatted message
6. Errors are logged per-user and error notifications sent to each user's Telegram

### Configuration System

- **Config Loading**: `Config` class (`src/config.py`) loads and validates `config.yaml`
- **Multi-User Support**: Configuration contains `users[]` array with per-user credentials
- **UserConfig Class**: Encapsulates individual user settings (id, name, enabled, oura, telegram)
- **Validation**: Checks for required fields, duplicate user IDs, and configuration structure
- **Properties**:
  - `config.users`: Returns all user configurations
  - `config.enabled_users`: Returns only enabled users
  - `config.get_user(user_id)`: Lookup specific user by ID
  - `config.azure`: Shared Azure OpenAI configuration
  - `config.scheduler`: Shared scheduler configuration

### Logging

- **Setup**: `setup_logger()` in `src/utils/logger.py` creates logger with console and rotating file handlers
- **Rotation**: 10MB max file size, 5 backup files
- **Levels**: Configurable via `config.yaml` (DEBUG, INFO, WARNING, ERROR)
- **Usage**: Get logger in modules via `get_logger(__name__)`

## Extending the System

### Adding a New Data Source

1. Create a new fetcher in `src/fetchers/`:
   ```python
   from .base import DataFetcher

   class MyFetcher(DataFetcher):
       def fetch_daily_data(self, target_date):
           # Implementation
           pass
   ```

2. Update `src/main.py` to initialize and use your fetcher:
   ```python
   self.fetcher = MyFetcher(...)
   ```

### Swapping the LLM Provider

1. Create a new analyzer in `src/analyzers/`:
   ```python
   from .base import DataAnalyzer

   class OpenAIAnalyzer(DataAnalyzer):
       def analyze(self, data):
           # Implementation
           pass
   ```

2. Update `src/main.py` to use your analyzer

### Adding a Notification Channel

1. Create a new notifier in `src/notifiers/`:
   ```python
   from .base import Notifier

   class EmailNotifier(Notifier):
       def send(self, message):
           # Implementation
           pass
   ```

2. Update `src/main.py` to use your notifier

## Important Notes

### Oura API Specifics

- **Data Timing**: Oura finalizes data the next day, so the system fetches **yesterday's data** by default
- **Rate Limiting**: Oura API has 100 requests/minute limit (enforced by `RateLimiter`)
- **Endpoints Used**:
  - `/v2/usercollection/daily_sleep`
  - `/v2/usercollection/daily_activity`
  - `/v2/usercollection/daily_readiness`
  - `/v2/usercollection/heartrate`
- **Heart Rate Aggregation**: Heart rate data returns multiple points, aggregated into min/max/avg in `_aggregate_heart_rate()`

### Azure OpenAI Specifics

- **System Prompt**: Instructs the model to format response in HTML for Telegram compatibility and keep responses within 1500 tokens
- **Token Limit**: Analysis summaries are constrained to 1500 tokens maximum (enforced via `max_tokens` parameter and explicit prompt instruction)
- **Prompt Construction**: `_construct_prompt()` formats health data into structured sections with markdown
- **HTML Cleanup**: Replaces `<br>` tags with newlines for Telegram
- **Format Sections**: Helper methods (`_format_sleep_data()`, etc.) convert raw API data into readable prompts

### Telegram Specifics

- **Message Length**: 4096 character limit, handled by `_split_long_message()`
- **Parsing Mode**: Uses HTML parsing (more reliable than Markdown for LLM output)
- **Fallback**: If HTML parsing fails, falls back to plain text
- **Async Handling**: Uses asyncio event loop for python-telegram-bot's async API
- **Retry Logic**: 3 retries with exponential backoff (2s, 4s, 8s)

### Configuration Requirements

Configuration follows multi-user format in `config.yaml`:

**Shared Resources (used by all users):**
- `azure.endpoint`, `azure.api_key`, `azure.deployment_name`
- `scheduler.hour`, `scheduler.minute`, `scheduler.timezone`
- `logging.level`, `logging.log_file`

**Per-User Configuration (in `users[]` array):**
- `id`: Unique user identifier
- `name`: Display name (optional)
- `enabled`: true/false (can disable without removing config)
- `oura.access_token`: User's Oura Ring API token
- `telegram.bot_token`: User's Telegram bot token
- `telegram.chat_id`: User's Telegram chat ID

**Example Structure:**
```yaml
azure:
  endpoint: "https://..."
  api_key: "..."
  deployment_name: "gpt-4"

scheduler:
  hour: 12
  minute: 0
  timezone: "UTC"

users:
  - id: "user_alice"
    name: "Alice"
    enabled: true
    oura:
      access_token: "ALICE_TOKEN"
    telegram:
      bot_token: "ALICE_BOT"
      chat_id: "ALICE_CHAT"

  - id: "user_bob"
    name: "Bob"
    enabled: true
    oura:
      access_token: "BOB_TOKEN"
    telegram:
      bot_token: "BOB_BOT"
      chat_id: "BOB_CHAT"
```

## Deployment

The system is designed to run as a systemd service on Linux (Proxmox LXC). See README.md for complete deployment instructions including:
- Creating the systemd service file
- Setting working directory to `/opt/health-assistant`
- Using virtual environment at `/opt/health-assistant/venv`

## Python Version

Requires Python 3.14+ (as specified in README.md)
