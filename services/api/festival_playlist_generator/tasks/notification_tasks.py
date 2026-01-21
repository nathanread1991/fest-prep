"""Celery tasks for notification processing."""

from typing import List
from datetime import datetime, timedelta
from celery import Celery

from festival_playlist_generator.core.celery_app import celery_app
from festival_playlist_generator.core.database import get_db
from festival_playlist_generator.services.notification_service import NotificationService
from festival_playlist_generator.services.recommendation_engine import RecommendationEngine
from festival_playlist_generator.models.user import User
from festival_playlist_generator.models.festival import Festival


@celery_app.task(name="send_daily_recommendations")
def send_daily_recommendations():
    """Send daily personalized recommendations to users."""
    db = next(get_db())
    
    try:
        notification_service = NotificationService(db)
        recommendation_engine = RecommendationEngine(db)
        
        # Get users who want daily recommendations
        users = db.query(User).all()
        
        for user in users:
            try:
                # Get user's notification preferences
                preferences = notification_service.get_notification_preferences(str(user.id))
                rec_prefs = preferences.get("recommendation", {})
                
                if (rec_prefs.get("frequency") == "daily" and 
                    (rec_prefs.get("email_enabled") or rec_prefs.get("push_enabled"))):
                    
                    # Get recommendations for user
                    recommendations = recommendation_engine.recommend_festivals(str(user.id), limit=3)
                    
                    if recommendations:
                        # Convert to dict format for notification
                        rec_data = []
                        for rec in recommendations:
                            rec_data.append({
                                "festival_id": rec.festival_id,
                                "festival_name": rec.festival_name,
                                "similarity_score": rec.similarity_score,
                                "location": rec.location,
                                "dates": [date.isoformat() for date in rec.dates]
                            })
                        
                        # Send notification
                        notification_service.send_recommendation_notification(
                            str(user.id), rec_data
                        )
                        
            except Exception as e:
                print(f"Failed to send recommendations to user {user.id}: {e}")
                continue
    
    finally:
        db.close()


@celery_app.task(name="send_weekly_recommendations")
def send_weekly_recommendations():
    """Send weekly personalized recommendations to users."""
    db = next(get_db())
    
    try:
        notification_service = NotificationService(db)
        recommendation_engine = RecommendationEngine(db)
        
        # Get users who want weekly recommendations
        users = db.query(User).all()
        
        for user in users:
            try:
                # Get user's notification preferences
                preferences = notification_service.get_notification_preferences(str(user.id))
                rec_prefs = preferences.get("recommendation", {})
                
                if (rec_prefs.get("frequency") == "weekly" and 
                    (rec_prefs.get("email_enabled") or rec_prefs.get("push_enabled"))):
                    
                    # Get more recommendations for weekly digest
                    recommendations = recommendation_engine.recommend_festivals(str(user.id), limit=5)
                    
                    if recommendations:
                        # Convert to dict format for notification
                        rec_data = []
                        for rec in recommendations:
                            rec_data.append({
                                "festival_id": rec.festival_id,
                                "festival_name": rec.festival_name,
                                "similarity_score": rec.similarity_score,
                                "location": rec.location,
                                "dates": [date.isoformat() for date in rec.dates],
                                "matching_artists": rec.matching_artists,
                                "recommended_artists": rec.recommended_artists
                            })
                        
                        # Send notification
                        notification_service.send_recommendation_notification(
                            str(user.id), rec_data
                        )
                        
            except Exception as e:
                print(f"Failed to send weekly recommendations to user {user.id}: {e}")
                continue
    
    finally:
        db.close()


@celery_app.task(name="check_new_festivals")
def check_new_festivals():
    """Check for new festivals and send notifications."""
    db = next(get_db())
    
    try:
        notification_service = NotificationService(db)
        
        # Get festivals announced in the last 24 hours
        yesterday = datetime.utcnow() - timedelta(days=1)
        new_festivals = (
            db.query(Festival)
            .filter(Festival.created_at >= yesterday)
            .all()
        )
        
        for festival in new_festivals:
            try:
                # Send announcement notifications
                notification_service.send_festival_announcement_notification(
                    str(festival.id)
                )
                
            except Exception as e:
                print(f"Failed to send announcement for festival {festival.id}: {e}")
                continue
    
    finally:
        db.close()


@celery_app.task(name="check_lineup_updates")
def check_lineup_updates():
    """Check for festival lineup updates and send notifications."""
    db = next(get_db())
    
    try:
        notification_service = NotificationService(db)
        
        # Get festivals updated in the last 24 hours
        yesterday = datetime.utcnow() - timedelta(days=1)
        updated_festivals = (
            db.query(Festival)
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
                    notification_service.send_artist_lineup_notification(
                        str(festival.id), new_artists
                    )
                    
            except Exception as e:
                print(f"Failed to send lineup update for festival {festival.id}: {e}")
                continue
    
    finally:
        db.close()


@celery_app.task(name="cleanup_old_notifications")
def cleanup_old_notifications():
    """Clean up old notification data."""
    # This would clean up old notification records from the database
    # For now, just log that cleanup would happen
    print("Cleaning up old notifications (placeholder)")


# Schedule periodic tasks
from celery.schedules import crontab

celery_app.conf.beat_schedule = {
    'daily-recommendations': {
        'task': 'send_daily_recommendations',
        'schedule': crontab(hour=9, minute=0),  # 9 AM daily
    },
    'weekly-recommendations': {
        'task': 'send_weekly_recommendations', 
        'schedule': crontab(hour=9, minute=0, day_of_week=1),  # 9 AM on Mondays
    },
    'check-new-festivals': {
        'task': 'check_new_festivals',
        'schedule': crontab(minute='*/30'),  # Every 30 minutes
    },
    'check-lineup-updates': {
        'task': 'check_lineup_updates',
        'schedule': crontab(hour='*/2'),  # Every 2 hours
    },
    'cleanup-notifications': {
        'task': 'cleanup_old_notifications',
        'schedule': crontab(hour=2, minute=0),  # 2 AM daily
    },
}