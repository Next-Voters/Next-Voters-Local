"""
Supabase client utilities for Next Voters Local pipeline.

This module provides functions to query Supabase for:
- Supported cities (from supported_cities table)
- Subscribers with their city preferences (from subscriptions table)
"""

import os
import logging
from typing import Any

from supabase import create_client, Client

logger = logging.getLogger(__name__)


def get_supabase_client() -> Client:
    """
    Create and return a Supabase client from environment variables.

    Returns:
        Supabase Client object

    Raises:
        ValueError: If SUPABASE_URL or SUPABASE_KEY environment variables are not set
    """
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")

    if not supabase_url:
        raise ValueError(
            "SUPABASE_URL environment variable is not set. "
            "Please set it to your Supabase project URL (e.g., https://project.supabase.co)"
        )

    if not supabase_key:
        raise ValueError(
            "SUPABASE_KEY environment variable is not set. "
            "Please set it to your Supabase API key."
        )

    logger.debug(f"Connecting to Supabase at {supabase_url}")
    return create_client(supabase_url, supabase_key)


def get_supported_cities_from_db() -> list[str]:
    """
    Query the supported_cities table from Supabase.

    Returns:
        List of city names sorted alphabetically

    Raises:
        ValueError: If Supabase credentials are missing
        Exception: If the database query fails
    """
    try:
        client = get_supabase_client()

        logger.info("Querying supported cities from Supabase...")
        response = (
            client.table("supported_cities").select("city").order("city").execute()
        )

        cities = [row["city"] for row in response.data]
        logger.info(f"Successfully retrieved {len(cities)} supported cities: {cities}")

        return cities

    except ValueError as e:
        logger.error(f"Supabase configuration error: {e}")
        raise
    except Exception as e:
        logger.error(f"Failed to query supported cities from Supabase: {e}")
        raise


def get_all_subscribers_with_cities() -> list[dict[str, Any]]:
    """
    Query all subscribers with their city preferences from Supabase.

    Returns:
        List of dicts with keys: "contact" (email), "city" (city name)
        Example: [
            {"contact": "user@example.com", "city": "Toronto"},
            {"contact": "another@example.com", "city": "New York City"},
            ...
        ]

    Raises:
        ValueError: If Supabase credentials are missing
        Exception: If the database query fails
    """
    try:
        client = get_supabase_client()

        logger.info("Querying subscribers from Supabase...")
        response = client.table("subscriptions").select("contact, city").execute()

        subscribers = response.data if response.data else []
        logger.info(f"Successfully retrieved {len(subscribers)} subscribers")

        # Log breakdown by city
        cities_count = {}
        for subscriber in subscribers:
            city = subscriber.get("city")
            if city:
                cities_count[city] = cities_count.get(city, 0) + 1

        for city, count in sorted(cities_count.items()):
            logger.debug(f"  {city}: {count} subscriber(s)")

        return subscribers

    except ValueError as e:
        logger.error(f"Supabase configuration error: {e}")
        raise
    except Exception as e:
        logger.error(f"Failed to query subscribers from Supabase: {e}")
        raise


def get_subscribers_for_city(city: str) -> list[str]:
    """
    Query subscribers for a specific city.

    Args:
        city: City name to filter by

    Returns:
        List of email addresses for subscribers in that city

    Raises:
        ValueError: If Supabase credentials are missing
        Exception: If the database query fails
    """
    try:
        client = get_supabase_client()

        logger.debug(f"Querying subscribers for city: {city}")
        response = (
            client.table("subscriptions").select("contact").eq("city", city).execute()
        )

        emails = [row["contact"] for row in response.data]
        logger.debug(f"Found {len(emails)} subscriber(s) for {city}")

        return emails

    except ValueError as e:
        logger.error(f"Supabase configuration error: {e}")
        raise
    except Exception as e:
        logger.error(f"Failed to query subscribers for city {city}: {e}")
        raise
