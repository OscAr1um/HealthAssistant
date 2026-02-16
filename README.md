# Health Assistant 🏥

A modular daily health monitoring system that fetches data from your Oura Ring, analyzes it with Azure OpenAI, and sends personalized health summaries via Telegram.

## Features

- 📊 **Comprehensive Health Data**: Fetches sleep, activity, readiness, and heart rate data from Oura Ring
- 🤖 **AI-Powered Analysis**: Uses Azure OpenAI to generate personalized insights and recommendations
- 📱 **Telegram Notifications**: Delivers daily summaries directly to your Telegram
- ⏰ **Automated Scheduling**: Runs daily at your configured time
- 👥 **Multi-User Support**: Monitor health for multiple users with a single deployment
- 🔧 **Modular Architecture**: Easy to extend with new data sources, analyzers, or notification channels
- 🐳 **Container Ready**: Designed to run on Proxmox LXC or any Linux environment

## Multi-User Support

Health Assistant supports monitoring multiple users with a single deployment. Each user:
- Has their own Oura Ring token and Telegram bot/chat
- Receives personalized health summaries independently
- Can be enabled/disabled without affecting others
- Shares the same Azure OpenAI deployment (cost-effective)
- Runs on the same daily schedule

**Example use cases:**
- Family health monitoring (parents and children)
- Couples tracking fitness together
- Small teams/groups with shared health goals

See the [Multi-User Configuration](#multi-user-configuration) section for setup instructions.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Health Assistant Service                  │
│                                                              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐ │
│  │ Data Fetcher │───▶│   Analyzer   │───▶│  Notifier    │ │
│  │   (Oura)     │    │   (Azure)    │    │  (Telegram)  │ │
│  └──────────────┘    └──────────────┘    └──────────────┘ │
│         │                    │                   │          │
│         └────────────────────┴───────────────────┘          │
│                          Scheduler                           │
│                       (APScheduler)                          │
└─────────────────────────────────────────────────────────────┘
```

## Requirements

- Python 3.14+
- Oura Ring with API access
- Azure OpenAI subscription
- Telegram bot

## Installation

### 1. Clone the Repository

```bash
git clone <repository-url>
cd HealthAssistant
```

### 2. Install Python Dependencies

```bash
pip install -r requirements.txt
```

Or use a virtual environment (recommended):

```bash
python3.14 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Setup Configuration

Copy the example configuration file:

```bash
cp config.yaml.example config.yaml
```

Edit `config.yaml` and fill in your credentials:

#### 3.1 Oura Ring Configuration

1. Go to https://cloud.ouraring.com/personal-access-tokens
2. Generate a new Personal Access Token
3. Copy the token to `oura.access_token` in config.yaml

```yaml
oura:
  access_token: "YOUR_OURA_PERSONAL_ACCESS_TOKEN"
```

#### 3.2 Azure OpenAI Configuration

1. Go to [Azure Portal](https://portal.azure.com)
2. Navigate to your Azure OpenAI resource
3. Get your endpoint URL and API key from "Keys and Endpoint"
4. Note your deployment name (the name you gave when deploying a model)

```yaml
azure:
  endpoint: "https://YOUR_RESOURCE.openai.azure.com/"
  api_key: "YOUR_AZURE_API_KEY"
  deployment_name: "gpt-4"  # Your deployment name
```

#### 3.3 Telegram Configuration

1. **Create a Telegram Bot**:
   - Open Telegram and search for [@BotFather](https://t.me/BotFather)
   - Send `/newbot` and follow the prompts
   - Copy the bot token provided

2. **Get Your Chat ID**:
   - Send a message to your new bot
   - Send a message to [@userinfobot](https://t.me/userinfobot)
   - Copy your chat ID

```yaml
telegram:
  bot_token: "YOUR_TELEGRAM_BOT_TOKEN"
  chat_id: "YOUR_TELEGRAM_CHAT_ID"
```

#### 3.4 Scheduler Configuration

Set your preferred time and timezone:

```yaml
scheduler:
  hour: 12
  minute: 0
  timezone: "America/New_York"  # Change to your timezone
```

Common timezones:
- `UTC`
- `America/New_York`
- `America/Los_Angeles`
- `Europe/London`
- `Europe/Paris`
- `Asia/Shanghai`
- `Asia/Tokyo`

## Multi-User Configuration

Health Assistant supports monitoring multiple users. You can configure multiple people to each receive their own personalized health summaries.

### Setting Up Multiple Users

1. **Create the multi-user config structure**:

```bash
# Option 1: Start with multi-user example
cp config.yaml.example.multi config.yaml

# Option 2: Migrate existing single-user config
python scripts/migrate_config.py config.yaml
```

2. **Edit `config.yaml`** with your users' credentials:

```yaml
# Shared resources (used by all users)
azure:
  endpoint: "https://YOUR_RESOURCE.openai.azure.com/"
  api_key: "YOUR_AZURE_API_KEY"
  deployment_name: "gpt-4"

scheduler:
  hour: 12
  minute: 0
  timezone: "UTC"

# Individual users
users:
  - id: "user_alice"
    name: "Alice"
    enabled: true
    oura:
      access_token: "ALICE_OURA_TOKEN"
    telegram:
      bot_token: "ALICE_BOT_TOKEN"
      chat_id: "ALICE_CHAT_ID"

  - id: "user_bob"
    name: "Bob"
    enabled: true
    oura:
      access_token: "BOB_OURA_TOKEN"
    telegram:
      bot_token: "BOB_BOT_TOKEN"
      chat_id: "BOB_CHAT_ID"
```

### Adding a New User

To add another user to an existing configuration:

1. Add a new entry to the `users:` array
2. Assign a unique `id` (e.g., "user_charlie")
3. Get their Oura token from https://cloud.ouraring.com/personal-access-tokens
4. Create a Telegram bot for them (or use a shared bot with different chat_id)
5. Set `enabled: true`
6. Restart Health Assistant

### Disabling a User Temporarily

To temporarily disable a user without removing their configuration:

```yaml
- id: "user_alice"
  enabled: false  # Alice won't receive health summaries
  # ... rest of config stays the same
```

### User Isolation

- Each user's health check runs independently
- If one user's check fails, others continue normally
- Each user receives error notifications only to their own chat
- Fresh LLM conversation for each user (no shared state)

### Backward Compatibility

**Existing single-user configs still work!** The system automatically detects legacy configurations and migrates them to a single default user. You'll see a warning in the logs:

```
WARNING: Detected legacy single-user configuration. Automatically migrating...
```

To migrate manually and add more users:

```bash
python scripts/migrate_config.py config.yaml
# Edit config.yaml to add more users
```

## Usage

### Test Run (Immediate Execution)

Test the system with an immediate execution:

```bash
python -m src.main --now
```

This will:
1. Fetch yesterday's health data from Oura Ring
2. Analyze it with Azure OpenAI
3. Send the summary to your Telegram

### Production Run (Scheduled Service)

Start the service to run daily at your configured time:

```bash
python -m src.main
```

The service will:
- Run in the foreground
- Execute daily at your configured time
- Log all activities to console and log file

Press `Ctrl+C` to stop the service.

## Deployment on Proxmox LXC

### 1. Create LXC Container

Create an Ubuntu or Debian LXC container in Proxmox.

### 2. Install Python 3.14

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Python 3.14 (adjust based on availability)
sudo apt install python3.14 python3.14-venv python3-pip -y
```

### 3. Clone and Setup

```bash
# Clone repository
git clone <repository-url> /opt/health-assistant
cd /opt/health-assistant

# Create virtual environment
python3.14 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Setup configuration
cp config.yaml.example config.yaml
nano config.yaml  # Edit with your credentials
```

### 4. Create Systemd Service

Create `/etc/systemd/system/health-assistant.service`:

```ini
[Unit]
Description=Health Assistant Daily Summary Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/health-assistant
Environment="PATH=/opt/health-assistant/venv/bin"
ExecStart=/opt/health-assistant/venv/bin/python -m src.main
Restart=on-failure
RestartSec=10s

[Install]
WantedBy=multi-user.target
```

### 5. Enable and Start Service

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable service to start on boot
sudo systemctl enable health-assistant

# Start service
sudo systemctl start health-assistant

# Check status
sudo systemctl status health-assistant

# View logs
sudo journalctl -u health-assistant -f
```

## Customization

### Adding New Data Sources

Create a new fetcher by inheriting from `DataFetcher`:

```python
# src/fetchers/apple_health.py
from .base import DataFetcher

class AppleHealthFetcher(DataFetcher):
    def fetch_daily_data(self, target_date):
        # Your implementation
        pass
```

Then update `src/main.py` to use your new fetcher.

### Swapping LLM Providers

Create a new analyzer by inheriting from `DataAnalyzer`:

```python
# src/analyzers/openai.py
from .base import DataAnalyzer

class OpenAIAnalyzer(DataAnalyzer):
    def analyze(self, data):
        # Your implementation
        pass
```

### Adding Notification Channels

Create a new notifier by inheriting from `Notifier`:

```python
# src/notifiers/email.py
from .base import Notifier

class EmailNotifier(Notifier):
    def send(self, message):
        # Your implementation
        pass
```

## Troubleshooting

### Configuration Errors

**Error: Configuration file not found**
```
Solution: Create config.yaml from config.yaml.example
cp config.yaml.example config.yaml
```

**Error: Missing required configuration field**
```
Solution: Verify all required fields in config.yaml are filled in
```

### Oura API Issues

**Error: 401 Unauthorized**
```
Solution: Verify your Oura access token is correct and hasn't expired
```

**Error: No data available**
```
Solution: Oura data is finalized the next day. The system fetches yesterday's data.
Ensure you wore your ring yesterday.
```

### Azure OpenAI Issues

**Error: Authentication failed**
```
Solution: Verify your Azure endpoint URL and API key are correct
```

**Error: Deployment not found**
```
Solution: Ensure the deployment_name in config.yaml matches your Azure deployment
```

### Telegram Issues

**Error: Bot token is invalid**
```
Solution: Get a new token from @BotFather
```

**Error: Chat not found**
```
Solution:
1. Send a message to your bot first
2. Verify your chat_id is correct
3. Make sure chat_id is a string in config.yaml
```

### Scheduler Issues

**Service doesn't run at scheduled time**
```
Solution:
1. Check timezone configuration in config.yaml
2. Verify system time: date
3. Check logs: journalctl -u health-assistant -f
```

## Logs

Logs are written to:
- **Console**: All log levels
- **File**: `health_assistant.log` (configurable in config.yaml)

Log rotation is automatic (10MB max file size, 5 backups).

To view logs in real-time:

```bash
# If running directly
tail -f health_assistant.log

# If running as systemd service
journalctl -u health-assistant -f
```

## Project Structure

```
HealthAssistant/
├── config.yaml.example          # Example configuration (single-user)
├── config.yaml.example.multi    # Example configuration (multi-user)
├── config.yaml                  # Your configuration (gitignored)
├── requirements.txt             # Python dependencies
├── README.md                    # This file
├── scripts/
│   └── migrate_config.py        # Migration helper for multi-user config
├── src/
│   ├── __init__.py
│   ├── main.py                  # Main application
│   ├── config.py                # Configuration loader (multi-user support)
│   ├── fetchers/
│   │   ├── __init__.py
│   │   ├── base.py              # Abstract base class
│   │   └── oura.py              # Oura Ring API client
│   ├── analyzers/
│   │   ├── __init__.py
│   │   ├── base.py              # Abstract base class
│   │   └── azure_openai.py      # Azure OpenAI analyzer
│   ├── notifiers/
│   │   ├── __init__.py
│   │   ├── base.py              # Abstract base class
│   │   └── telegram.py          # Telegram notifier
│   └── utils/
│       ├── __init__.py
│       ├── logger.py            # Logging utilities
│       └── rate_limiter.py      # API rate limiting
└── tests/                       # Future test suite
```

## License

This project is for personal use.

## Contributing

This is a personal project, but feel free to fork and customize for your own needs.

## Support

For issues related to:
- **Oura Ring API**: https://cloud.ouraring.com/docs
- **Azure OpenAI**: https://learn.microsoft.com/en-us/azure/ai-services/openai/
- **Telegram Bots**: https://core.telegram.org/bots

## Acknowledgments

- Oura Ring for the health data API
- OpenAI for the powerful language models
- Telegram for the bot platform
