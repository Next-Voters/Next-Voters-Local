"""MCP/search client utilities for connecting to external services."""

from utils.mcp.tavily_client import (
    get_api_key,
    get_tavily_session,
    load_search_profile,
    search_with_profile,
    search_legislation,
    search_political_content,
    extract_search_results,
    extract_url_content,
)
from utils.mcp.twitter_client import (
    get_twitter_session,
    get_twitter_credentials,
    search_tweets,
    get_user_tweets,
    get_user_by_username,
    search_user_and_tweets,
    validate_twitter_handle,
    sanitize_search_context,
    is_error_response,
    extract_tweet_results,
    SMITHERY_TWITTER_URL,
)

__all__ = [
    "get_api_key",
    "get_tavily_session",
    "load_search_profile",
    "search_with_profile",
    "search_legislation",
    "search_political_content",
    "extract_search_results",
    "extract_url_content",
    "get_twitter_session",
    "get_twitter_credentials",
    "search_tweets",
    "get_user_tweets",
    "get_user_by_username",
    "search_user_and_tweets",
    "validate_twitter_handle",
    "sanitize_search_context",
    "is_error_response",
    "extract_tweet_results",
    "SMITHERY_TWITTER_URL",
]
