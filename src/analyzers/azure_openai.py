"""Azure OpenAI data analyzer."""

from typing import Any, Dict

from openai import AzureOpenAI

from ..analyzers.base import DataAnalyzer
from ..utils.logger import get_logger


class AzureOpenAIAnalyzer(DataAnalyzer):
    """Analyzer that uses Azure OpenAI to generate health insights."""

    def __init__(
        self,
        endpoint: str,
        api_key: str,
        deployment_name: str,
        api_version: str = "2024-02-01",
        model: str = "gpt-4",
        temperature: float = 0.7,
        max_tokens: int = 1500,
    ):
        """
        Initialize Azure OpenAI analyzer.

        Args:
            endpoint: Azure OpenAI endpoint URL
            api_key: Azure OpenAI API key
            deployment_name: Name of the deployment in Azure
            api_version: API version to use
            model: Model name
            temperature: Sampling temperature (0-1)
            max_tokens: Maximum tokens in response
        """
        self.endpoint = endpoint
        self.api_key = api_key
        self.deployment_name = deployment_name
        self.api_version = api_version
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.logger = get_logger(__name__)

        # Initialize Azure OpenAI client
        self.client = AzureOpenAI(
            azure_endpoint=endpoint,
            api_key=api_key,
            api_version=api_version,
        )

    def analyze(self, data: Dict[str, Any]) -> str:
        """
        Analyze health data using Azure OpenAI.

        Args:
            data: Dictionary containing health data from Oura Ring

        Returns:
            Comprehensive health summary as formatted text

        Raises:
            Exception: If analysis fails
        """
        self.logger.info("Starting health data analysis with Azure OpenAI")

        try:
            prompt = self._construct_prompt(data)
            self.logger.debug(f"Constructed prompt with {len(prompt)} characters")

            response = self.client.chat.completions.create(
                model=self.deployment_name,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a knowledgeable health and wellness assistant. "
                            "Your role is to analyze health data from wearable devices and provide "
                            "comprehensive, actionable insights. Focus on trends, patterns, and "
                            "personalized recommendations. Be encouraging but honest about areas "
                            "that need improvement. Format your response in clear sections with "
                            "HTML formatting for Telegram. Use <b>bold</b>, <i>italic</i>, "
                            "<code>code</code>, and <pre>preformatted</pre> tags. Use proper line breaks."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )

            summary = response.choices[0].message.content
            self.logger.info("Successfully generated health analysis")

            return summary

        except Exception as e:
            self.logger.error(f"Failed to analyze health data: {e}")
            raise Exception(f"Azure OpenAI analysis failed: {e}")

    def _construct_prompt(self, data: Dict[str, Any]) -> str:
        """
        Construct detailed prompt from health data.

        Args:
            data: Health data dictionary

        Returns:
            Formatted prompt string
        """
        date_str = data.get("date", "Unknown date")

        # Extract sleep data
        sleep = data.get("sleep", {})
        sleep_section = self._format_sleep_data(sleep)

        # Extract activity data
        activity = data.get("activity", {})
        activity_section = self._format_activity_data(activity)

        # Extract readiness data
        readiness = data.get("readiness", {})
        readiness_section = self._format_readiness_data(readiness)

        # Extract heart rate data
        heart_rate = data.get("heart_rate", {})
        hr_section = self._format_heart_rate_data(heart_rate)

        prompt = f"""Please analyze my health data for {date_str} and provide a comprehensive daily summary with personalized insights and recommendations.

{sleep_section}

{activity_section}

{readiness_section}

{hr_section}

Please provide:
1. <b>Overall Health Summary</b>: A brief overview of my day's health metrics
2. <b>Sleep Analysis</b>: Detailed insights about sleep quality, duration, and recommendations
3. <b>Activity Analysis</b>: Assessment of physical activity levels and suggestions
4. <b>Recovery & Readiness</b>: Evaluation of recovery status and what it means for today
5. <b>Heart Rate Insights</b>: Analysis of heart rate patterns and cardiovascular health indicators
6. <b>Key Recommendations</b>: 3-5 actionable suggestions to improve my health based on today's data
7. <b>Trends & Patterns</b>: Any notable patterns or areas of concern

Format the response in HTML for Telegram. Use <b>bold</b> for headers and emphasis, bullet points with proper line breaks, and clear sections. Be specific, encouraging, and actionable."""

        return prompt

    def _format_sleep_data(self, sleep: Dict[str, Any]) -> str:
        """Format sleep data for prompt."""
        if not sleep:
            return "**Sleep Data**: No sleep data available for this date."

        sections = ["**Sleep Data**:"]

        # Core sleep metrics
        if "score" in sleep:
            sections.append(f"- Sleep Score: {sleep['score']}/100")

        if "total_sleep_duration" in sleep:
            hours = sleep["total_sleep_duration"] / 3600
            sections.append(f"- Total Sleep Duration: {hours:.1f} hours")

        if "efficiency" in sleep:
            sections.append(f"- Sleep Efficiency: {sleep['efficiency']}%")

        if "restfulness" in sleep:
            sections.append(f"- Restfulness: {sleep['restfulness']}%")

        # Sleep stages
        if "rem_sleep_duration" in sleep:
            rem_hours = sleep["rem_sleep_duration"] / 3600
            sections.append(f"- REM Sleep: {rem_hours:.1f} hours")

        if "deep_sleep_duration" in sleep:
            deep_hours = sleep["deep_sleep_duration"] / 3600
            sections.append(f"- Deep Sleep: {deep_hours:.1f} hours")

        if "light_sleep_duration" in sleep:
            light_hours = sleep["light_sleep_duration"] / 3600
            sections.append(f"- Light Sleep: {light_hours:.1f} hours")

        # Additional metrics
        if "latency" in sleep:
            sections.append(f"- Sleep Latency: {sleep['latency'] / 60:.0f} minutes")

        if "average_heart_rate" in sleep:
            sections.append(f"- Average Heart Rate (sleep): {sleep['average_heart_rate']} bpm")

        if "lowest_heart_rate" in sleep:
            sections.append(f"- Lowest Heart Rate: {sleep['lowest_heart_rate']} bpm")

        if "average_hrv" in sleep:
            sections.append(f"- Average HRV: {sleep['average_hrv']} ms")

        return "\n".join(sections)

    def _format_activity_data(self, activity: Dict[str, Any]) -> str:
        """Format activity data for prompt."""
        if not activity:
            return "**Activity Data**: No activity data available for this date."

        sections = ["**Activity Data**:"]

        if "score" in activity:
            sections.append(f"- Activity Score: {activity['score']}/100")

        if "steps" in activity:
            sections.append(f"- Steps: {activity['steps']:,}")

        if "active_calories" in activity:
            sections.append(f"- Active Calories: {activity['active_calories']} kcal")

        if "total_calories" in activity:
            sections.append(f"- Total Calories: {activity['total_calories']} kcal")

        if "equivalent_walking_distance" in activity:
            km = activity["equivalent_walking_distance"] / 1000
            sections.append(f"- Walking Distance: {km:.2f} km")

        if "high_activity_time" in activity:
            high_min = activity["high_activity_time"] / 60
            sections.append(f"- High Activity Time: {high_min:.0f} minutes")

        if "medium_activity_time" in activity:
            med_min = activity["medium_activity_time"] / 60
            sections.append(f"- Medium Activity Time: {med_min:.0f} minutes")

        if "low_activity_time" in activity:
            low_min = activity["low_activity_time"] / 60
            sections.append(f"- Low Activity Time: {low_min:.0f} minutes")

        if "sedentary_time" in activity:
            sed_min = activity["sedentary_time"] / 60
            sections.append(f"- Sedentary Time: {sed_min:.0f} minutes")

        if "average_met_minutes" in activity:
            sections.append(f"- Average MET: {activity['average_met_minutes']:.1f}")

        return "\n".join(sections)

    def _format_readiness_data(self, readiness: Dict[str, Any]) -> str:
        """Format readiness data for prompt."""
        if not readiness:
            return "**Readiness Data**: No readiness data available for this date."

        sections = ["**Readiness Data**:"]

        if "score" in readiness:
            sections.append(f"- Readiness Score: {readiness['score']}/100")

        if "temperature_deviation" in readiness:
            sections.append(
                f"- Temperature Deviation: {readiness['temperature_deviation']:+.2f}°C"
            )

        # Contributing factors
        contributors = readiness.get("contributors", {})
        if contributors:
            sections.append("- Contributing Factors:")

            if "activity_balance" in contributors:
                sections.append(f"  - Activity Balance: {contributors['activity_balance']}/100")

            if "body_temperature" in contributors:
                sections.append(f"  - Body Temperature: {contributors['body_temperature']}/100")

            if "hrv_balance" in contributors:
                sections.append(f"  - HRV Balance: {contributors['hrv_balance']}/100")

            if "previous_day_activity" in contributors:
                sections.append(
                    f"  - Previous Day Activity: {contributors['previous_day_activity']}/100"
                )

            if "previous_night" in contributors:
                sections.append(f"  - Previous Night: {contributors['previous_night']}/100")

            if "recovery_index" in contributors:
                sections.append(f"  - Recovery Index: {contributors['recovery_index']}/100")

            if "resting_heart_rate" in contributors:
                sections.append(
                    f"  - Resting Heart Rate: {contributors['resting_heart_rate']}/100"
                )

            if "sleep_balance" in contributors:
                sections.append(f"  - Sleep Balance: {contributors['sleep_balance']}/100")

        return "\n".join(sections)

    def _format_heart_rate_data(self, heart_rate: Dict[str, Any]) -> str:
        """Format heart rate data for prompt."""
        if not heart_rate:
            return "**Heart Rate Data**: No heart rate data available for this date."

        sections = ["**Heart Rate Data**:"]

        if "min_hr" in heart_rate:
            sections.append(f"- Minimum Heart Rate: {heart_rate['min_hr']:.0f} bpm")

        if "max_hr" in heart_rate:
            sections.append(f"- Maximum Heart Rate: {heart_rate['max_hr']:.0f} bpm")

        if "avg_hr" in heart_rate:
            sections.append(f"- Average Heart Rate: {heart_rate['avg_hr']:.0f} bpm")

        if "data_points" in heart_rate:
            sections.append(f"- Data Points Collected: {heart_rate['data_points']}")

        return "\n".join(sections)
