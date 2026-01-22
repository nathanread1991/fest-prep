"""Celery tasks for notification processing."""

import asyncio
from datetime import datetime, timedelta
from typing import Any, Callable, List, cast

from celery import Celery
from celery.schedules import crontab

from festival_playlist_generator.core.celery_app import celery_app
from festival_playlist_generator.core.database import get_db_session
from festival_playlist_generator.models.festival import Festival
from festival_playlist_generator.models.user import User
from festival_playlist_generator.services.notification_service import (
    NotificationService,
)
from festival_playlist_generator.services.recommendation_engine import (
    RecommendationEngine,
)


@celery_app.task(name="send_daily_recommendations")  # type: ignore[untyped-decorator]
def send_daily_recommendations() -> None:
    """Send daily personalized recommendations to users."""
    asyncio.run(_send_daily_recommendations())


async def _send_daily_recommendations() -> None:
    """Async implementation of send_daily_recommendations."""
    db_gen = get_db_session()
    db = await db_gen.__anext__()

    try:
        notification_service = NotificationService(db)  # type: ignore[arg-type]
        recommendation_engine = RecommendationEngine(db)  # type: ignore[arg-type]

        # Get users who want daily recommendations
        users = db.query(User).all()  # type: ignore[attr-defined]

        for user in users:
            try:
                # Get user's notification preferences
                preferences = await notification_service.get_notification_preferences(
                    str(user.id)
                )
                rec_prefs = preferences.get("recommendation", {})

                if rec_prefs.get("email_enabled") or rec_prefs.get("push_enabled"):

                    # Get recommendations for user
                    recommendations = await recommendation_engine.recommend_festivals(
                        str(user.id), limit=3
                    )

                    if recommendations:
                        # Convert to dict format for notification
                        rec_data = []
                        for rec in recommendations:
                            rec_data.append(
                                {
                                    "festival_id": rec.festival_id,
                                    "festival_name": rec.festival_name,
                                    "similarity_score": rec.similarity_score,
                                    "location": rec.location,
                                    "dates": [date.isoformat() for date in rec.dates],
                                }
                            )

                        # Send notification
                        await notification_service.send_recommendation_notification(
                            str(user.id), rec_data
                        )

            except Exception as e:
                print(f"Failed to send recommendations to user {user.id}: {e}")
                continue
    finally:
        await db.close()


@celery_app.task(name="send_weekly_recommendations")  # type: ignore[untyped-decorator]
def send_weekly_recommendations() -> None:
    """Send weekly personalized recommendations to users."""
    asyncio.run(_send_weekly_recommendations())


async def _send_weekly_recommendations() -> None:
    """Async implementation of send_weekly_recommendations."""
    db_gen = get_db_session()
    db = await db_gen.__anext__()

    try:
        notification_service = NotificationService(db)  # type: ignore[arg-type]
        recommendation_engine = RecommendationEngine(db)  # type: ignore[arg-type]

        # Get users who want weekly recommendations
        users = db.query(User).all()  # type: ignore[attr-defined]

        for user in users:
            try:
                # Get user's notification preferences
                preferences = await notification_service.get_notification_preferences(
                    str(user.id)
                )
                rec_prefs = preferences.get("recommendation", {})

                if rec_prefs.get("frequency") == "weekly" and (
                    rec_prefs.get("email_enabled") or rec_prefs.get("push_enabled")
                ):

                    # Get more recommendations for weekly digest
                    recommendations = await recommendation_engine.recommend_festivals(
                        str(user.id), limit=5
                    )

                    if recommendations:
                        # Convert to dict format for notification
                        rec_data = []
                        for rec in recommendations:
                            rec_data.append(
                                {
                                    "festival_id": rec.festival_id,
                                    "festival_name": rec.festival_name,
                                    "similarity_score": rec.similarity_score,
                                    "location": rec.location,
                                    "dates": [date.isoformat() for date in rec.dates],
                                    "matching_artists": rec.matching_artists,
                                    "recommended_artists": rec.recommended_artists,
                                }
                            )

                        # Send notification
                        await notification_service.send_recommendation_notification(
                            str(user.id), rec_data
                        )

            except Exception as e:
                print(f"Failed to send weekly recommendations to user {user.id}: {e}")
                continue
    finally:
        await db.close()


@celery_app.task(name="check_new_festivals")  # type: ignore[untyped-decorator]
def check_new_festivals() -> None:
    """Check for new festivals and send notifications."""
    asyncio.run(_check_new_festivals())


async def _check_new_festivals() -> None:
    """Async implementation of check_new_festivals."""
    db_gen = get_db_session()
    db = await db_gen.__anext__()

    try:
        notification_service = NotificationService(db)  # type: ignore[arg-type]

        # Get festivals announced in the last 24 hours
        yesterday = datetime.utcnow() - timedelta(days=1)
        new_festivals = (
            db.query(Festival).filter(Festival.created_at >= yesterday).all()  # type: ignore[attr-defined]
        )

        for festival in new_festivals:
            try:
                # Send announcement notifications
                await notification_service.send_festival_announcement_notification(
                    str(festival.id)
                )

            except Exception as e:
                print(f"Failed to send announcement for festival {festival.id}: {e}")
                continue
    finally:
        await db.close()


@celery_app.task(name="check_lineup_updates")  # type: ignore[untyped-decorator]
def check_lineup_updates() -> None:
    """Check for festival lineup updates and send notifications."""
    asyncio.run(_check_lineup_updates())


async def _check_lineup_updates() -> None:
    """Async implementation of check_lineup_updates."""
    db_gen = get_db_session()
    db = await db_gen.__anext__()

    try:
        notification_service = NotificationService(db)  # type: ignore[arg-type]

        # Get festivals updated in the last 24 hours
        yesterday = datetime.utcnow() - timedelta(days=1)
        updated_festivals = (
            db.query(Festival)  # type: ignore[attr-defined]
            .filter(Festival.updated_at >= yesterday)
            .filter(Festival.created_at < yesterday)  # Not newly created
            .all()
        )

        for festival in updated_festivals:
            try:
                # For this example, assume all artists are "new"
                # In a real implementation, you'd track what changed
                new_artists = festival.artists[-3:] if festival.artists else []

                if new_artists:
                    await notification_service.send_artist_lineup_notification(
                        str(festival.id), new_artists
                    )

            except Exception as e:
                print(f"Failed to send lineup update for festival {festival.id}: {e}")
                continue
    finally:
        await db.close()


@celery_app.task(name="cleanup_old_notifications")  # type: ignore[untyped-decorator]
def cleanup_old_notifications() -> None:
    """Clean up old notification data."""
    # This would clean up old notification records from the database
    # For now, just log that cleanup would happen
    print("Cleaning up old notifications (placeholder)")


# Schedule periodic tasks

celery_app.conf.beat_schedule = {
    "daily-recommendations": {
        "task": "send_daily_recommendations",
        "schedule": crontab(hour=9, minute=0),  # 9 AM daily
    },
    "weekly-recommendations": {
        "task": "send_weekly_recommendations",
        "schedule": crontab(hour=9, minute=0, day_of_week=1),  # 9 AM on Mondays
    },
    "check-new-festivals": {
        "task": "check_new_festivals",
        "schedule": crontab(minute="*/30"),  # Every 30 minutes
    },
    "check-lineup-updates": {
        "task": "check_lineup_updates",
        "schedule": crontab(hour="*/2"),  # Every 2 hours
    },
    "cleanup-notifications": {
        "task": "cleanup_old_notifications",
        "schedule": crontab(hour=2, minute=0),  # 2 AM daily
    },
}
