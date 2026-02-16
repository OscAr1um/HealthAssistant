"""Debug script to test Azure OpenAI and Oura data fetching."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from datetime import date, timedelta
from src.config import Config
from src.fetchers.oura import OuraFetcher
from src.analyzers.azure_openai import AzureOpenAIAnalyzer

def main():
    print("=" * 80)
    print("DEBUGGING HEALTH ASSISTANT")
    print("=" * 80)

    # Load config
    print("\n1. Loading configuration...")
    config = Config()
    print("✓ Config loaded")

    # Initialize Oura fetcher
    print("\n2. Initializing Oura fetcher...")
    oura_config = config.oura
    fetcher = OuraFetcher(
        access_token=oura_config["access_token"],
        user_id=oura_config.get("user_id"),
    )
    print("✓ Oura fetcher initialized")

    # Fetch data
    target_date = date.today() - timedelta(days=1)
    print(f"\n3. Fetching data for {target_date}...")
    health_data = fetcher.fetch_daily_data(target_date)

    print(f"\n✓ Data fetched:")
    print(f"  - Date: {health_data.get('date')}")
    print(f"  - Sleep data: {'YES' if health_data.get('sleep') else 'NO (EMPTY)'}")
    print(f"  - Activity data: {'YES' if health_data.get('activity') else 'NO (EMPTY)'}")
    print(f"  - Readiness data: {'YES' if health_data.get('readiness') else 'NO (EMPTY)'}")
    print(f"  - Heart rate data: {'YES' if health_data.get('heart_rate') else 'NO (EMPTY)'}")

    # Show sample data
    if health_data.get('sleep'):
        sleep = health_data['sleep']
        print(f"\n  Sleep sample: score={sleep.get('score')}, duration={sleep.get('total_sleep_duration')}s")

    # Initialize Azure analyzer
    print("\n4. Initializing Azure OpenAI analyzer...")
    azure_config = config.azure
    analyzer = AzureOpenAIAnalyzer(
        endpoint=azure_config["endpoint"],
        api_key=azure_config["api_key"],
        deployment_name=azure_config["deployment_name"],
        api_version=azure_config.get("api_version", "2024-02-01"),
        model=azure_config.get("model", "gpt-4"),
        temperature=azure_config.get("temperature", 0.7),
        max_tokens=azure_config.get("max_tokens", 1500),
    )
    print("✓ Analyzer initialized")
    print(f"  - Endpoint: {azure_config['endpoint']}")
    print(f"  - Deployment: {azure_config['deployment_name']}")
    print(f"  - Model: {azure_config.get('model', 'gpt-4')}")
    print(f"  - API Version: {azure_config.get('api_version', '2024-02-01')}")

    # Analyze data
    print("\n5. Analyzing data with Azure OpenAI...")
    print("   (This may take a few seconds...)")
    try:
        analysis = analyzer.analyze(health_data)

        if analysis:
            print(f"\n✓ Analysis received ({len(analysis)} characters)")
            print("\nFirst 500 characters of analysis:")
            print("-" * 80)
            print(analysis[:500])
            print("-" * 80)
        else:
            print("\n✗ PROBLEM: Analysis is empty or None!")
            print("   This means Azure OpenAI returned no content.")
    except Exception as e:
        print(f"\n✗ ERROR during analysis: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 80)
    print("DEBUG COMPLETE")
    print("=" * 80)

if __name__ == "__main__":
    main()
