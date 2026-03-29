"""
Email dispatcher for sending city-specific reports to subscribers.

This module handles the batch dispatch of markdown reports to subscribers
based on their city preferences. Unlike the email_sender.py node (which is
part of the pipeline chain), this dispatcher is called after all pipelines
complete and works with a global reports dictionary.

The dispatcher ensures each subscriber receives only the report for their
subscribed city.
"""

import json
import os
import time
import queue
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from email.mime.text import MIMEText
from threading import Lock
from typing import Any

from utils.supabase_client import get_all_subscribers_with_cities
from utils.email import (
    SMTPConnectionPool,
    convert_markdown_to_html,
    render_template,
    create_mime_message,
)

logger = logging.getLogger(__name__)


EMAIL_REQUIRED_ENV = (
    "SMTP_EMAIL",
    "SMTP_APP_PASSWORD",
    "SUPABASE_URL",
    "SUPABASE_KEY",
)


def _is_email_configured() -> bool:
    """Check if all required email environment variables are set."""
    return all(os.environ.get(env_var) for env_var in EMAIL_REQUIRED_ENV)


def send_single_email(
    pool: SMTPConnectionPool,
    email: str,
    subject: str,
    html_body: str,
    failures: queue.Queue,
) -> bool:
    """Send a single email and track failures.
    
    Uses a thread-safe queue instead of a shared list to avoid race conditions
    when multiple threads add failures simultaneously.
    
    Args:
        pool: SMTP connection pool
        email: Recipient email address
        subject: Email subject line
        html_body: HTML email body
        failures: Thread-safe queue for tracking delivery failures
        
    Returns:
        True if email sent successfully, False otherwise
    """
    conn = None
    try:
        conn = pool.get_connection(timeout=30)

        msg = create_mime_message(
            os.environ["SMTP_EMAIL"],
            email,
            subject,
            html_body,
        )

        conn.sendmail(os.environ["SMTP_EMAIL"], email, msg.as_string())

        time.sleep(0.5)

        return True
    except Exception as e:
        # Queue is thread-safe, no lock needed
        failures.put(
            {
                "email": email,
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )
        return False
    finally:
        if conn:
            pool.return_connection(conn)


def send_batch(
    pool: SMTPConnectionPool,
    emails: list[str],
    subject: str,
    html_body: str,
    failures: queue.Queue,
):
    """Send emails in a batch using thread pool.
    
    Args:
        pool: SMTP connection pool
        emails: List of recipient email addresses
        subject: Email subject line
        html_body: HTML email body
        failures: Thread-safe queue for tracking delivery failures
    """
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = []
        for email in emails:
            future = executor.submit(
                send_single_email,
                pool,
                email,
                subject,
                html_body,
                failures,
            )
            futures.append(future)
        for future in futures:
            future.result()


def save_failures(failures: list[dict]):
    """Save email delivery failures to a JSON file.
    
    Args:
        failures: List of failure records
    """
    if not failures:
        return
    failures_path = os.path.join(os.path.dirname(__file__), "..", "email_failures.json")
    with open(failures_path, "w") as f:
        json.dump(failures, f, indent=2)
    logger.warning(f"Saved {len(failures)} email delivery failures to {failures_path}")


def dispatch_emails_to_subscribers(
    reports_by_city: dict[str, str],
) -> dict[str, Any]:
    """
    Query all subscribers and send each their city-specific report.

    This function:
    1. Validates that reports_by_city is not empty
    2. Queries the subscriptions table for all subscribers with their city preferences
    3. For each subscriber, looks up their city's report from the reports_by_city dictionary
    4. Sends the city-specific markdown report to that subscriber
    5. Tracks delivery statistics and failures separately

    Args:
        reports_by_city: Dictionary mapping city names to markdown reports
                        Generated from build_city_reports_dict() in run_container_job.py
                        Example: {"Toronto": "# Report...", "NYC": "# Report..."}

    Returns:
        Dictionary with delivery statistics:
        {
            "total_sent": int,
            "by_city": {city: count, ...},
            "missing_reports": [{"email": "...", "city": "...", "reason": "...", "timestamp": "..."}],
            "delivery_failures": [{"email": "...", "error": "...", "timestamp": "..."}]
        }
    """

    # Check if email is configured
    if not _is_email_configured():
        logger.info("Email configuration incomplete; skipping email dispatch")
        return {
            "total_sent": 0,
            "by_city": {},
            "missing_reports": [],
            "delivery_failures": [
                "Email not configured - missing SMTP_EMAIL or SMTP_APP_PASSWORD"
            ],
        }

    # Validate input: reports_by_city should not be empty
    if not reports_by_city:
        logger.warning("No reports available for dispatch (reports_by_city is empty)")
        return {
            "total_sent": 0,
            "by_city": {},
            "missing_reports": [],
            "delivery_failures": ["No reports available for dispatch"],
        }

    # Query all subscribers with their city preferences
    try:
        subscribers = get_all_subscribers_with_cities()
    except Exception as e:
        logger.error(f"Failed to query subscribers: {e}")
        return {
            "total_sent": 0,
            "by_city": {},
            "missing_reports": [],
            "delivery_failures": [f"Failed to query subscribers: {str(e)}"],
        }

    if not subscribers:
        logger.info("No subscribers found")
        return {
            "total_sent": 0,
            "by_city": {},
            "missing_reports": [],
            "delivery_failures": [],
        }

    logger.info(f"Dispatching reports to {len(subscribers)} subscriber(s)")

    # Group subscribers by city and track missing reports
    subscribers_by_city: dict[str, list[str]] = {}
    missing_reports = []

    for subscriber in subscribers:
        contact = subscriber.get("contact")
        city = subscriber.get("city")

        if not contact or not city:
            logger.warning(f"Subscriber missing contact or city: {subscriber}")
            continue

        # Validate city has a non-empty name
        if not city or not city.strip():
            logger.warning(f"Subscriber has empty city name: {subscriber}")
            continue

        # Validate city has a report
        if city not in reports_by_city:
            logger.warning(f"No report available for city: {city}")
            missing_reports.append(
                {
                    "email": contact,
                    "city": city,
                    "reason": "No report available for city",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )
            continue

        # Add subscriber to city group
        if city not in subscribers_by_city:
            subscribers_by_city[city] = []
        subscribers_by_city[city].append(contact)

    # Set up email infrastructure with error handling
    try:
        pool = SMTPConnectionPool(pool_size=10)
    except RuntimeError as e:
        logger.error(f"Failed to initialize SMTP connection pool: {e}")
        return {
            "total_sent": 0,
            "by_city": {},
            "missing_reports": missing_reports,
            "delivery_failures": [f"SMTP pool initialization failed: {str(e)}"],
        }

    # Use thread-safe queue for failure tracking instead of shared list
    failures_queue: queue.Queue = queue.Queue()

    delivery_stats = {
        "total_sent": 0,
        "by_city": {},
        "missing_reports": missing_reports,
        "delivery_failures": [],
    }

    try:
        # Send emails grouped by city
        for city, emails in subscribers_by_city.items():
            markdown_report = reports_by_city[city]
            html_content = convert_markdown_to_html(markdown_report)
            html_body = render_template(html_content)

            logger.info(f"Sending {len(emails)} email(s) for city: {city}")

            # Send emails in waves to avoid rate limiting
            waves = [emails[i : i + 100] for i in range(0, len(emails), 100)]

            for wave in waves:
                send_batch(
                    pool,
                    wave,
                    f"NV Local Report - {city}",
                    html_body,
                    failures_queue,
                )
                time.sleep(1)

            # Update stats
            delivery_stats["by_city"][city] = len(emails)
            delivery_stats["total_sent"] += len(emails)

    finally:
        pool.close_all()

    # Extract failures from queue into list
    delivery_failures = []
    while not failures_queue.empty():
        try:
            delivery_failures.append(failures_queue.get_nowait())
        except queue.Empty:
            break

    # Save all failures (both missing reports and delivery failures)
    all_failures = delivery_failures + missing_reports
    save_failures(all_failures)

    # Update stats with delivery failures (separate from missing reports)
    delivery_stats["delivery_failures"] = delivery_failures

    logger.info(
        f"Email dispatch complete: {delivery_stats['total_sent']} sent, "
        f"{len(delivery_failures)} delivery failures, "
        f"{len(missing_reports)} missing reports"
    )

    return delivery_stats
