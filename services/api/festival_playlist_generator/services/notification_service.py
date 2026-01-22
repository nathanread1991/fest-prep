"""Notification service for email and web push notifications."""

import json
import smtplib
from dataclasses import dataclass
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from uuid import UUID

from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from festival_playlist_generator.core.config import settings
from festival_playlist_generator.models.artist import Artist
from festival_playlist_generator.models.festival import Festival
from festival_playlist_generator.models.user import User


class NotificationType(str, Enum):
    """Types of notifications."""

    FESTIVAL_ANNOUNCEMENT = "festival_announcement"
    ARTIST_LINEUP_UPDATE = "artist_lineup_update"
    PLAYLIST_READY = "playlist_ready"
    RECOMMENDATION = "recommendation"


class NotificationFrequency(str, Enum):
    """Notification frequency options."""

    IMMEDIATE = "immediate"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


@dataclass
class NotificationPreference:
    """User notification preferences."""

    user_id: str
    notification_type: NotificationType
    email_enabled: bool
    push_enabled: bool
    frequency: NotificationFrequency
    created_at: datetime


@dataclass
class Notification:
    """Notification message."""

    id: str
    user_id: str
    notification_type: NotificationType
    title: str
    message: str
    data: Dict[str, Any]
    created_at: datetime
    sent_at: Optional[datetime] = None
    email_sent: bool = False
    push_sent: bool = False


class NotificationService:
    """Service for managing notifications."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.smtp_server = getattr(settings, "SMTP_SERVER", "localhost")
        self.smtp_port = getattr(settings, "SMTP_PORT", 587)
        self.smtp_username = getattr(settings, "SMTP_USERNAME", "")
        self.smtp_password = getattr(settings, "SMTP_PASSWORD", "")
        self.from_email = getattr(
            settings, "FROM_EMAIL", "noreply@festivalplaylist.com"
        )

    async def send_festival_announcement_notification(
        self, festival_id: str, user_ids: Optional[List[str]] = None
    ) -> List[str]:
        """
        Send notifications about new festival announcements.

        Args:
            festival_id: Festival that was announced
            user_ids: Specific users to notify (if None, notify all eligible users)

        Returns:
            List of user IDs that were notified
        """
        festival = self.db.query(Festival).filter(Festival.id == festival_id).first()
        if not festival:
            raise ValueError(f"Festival {festival_id} not found")

        # Get users to notify
        if user_ids:
            users = self.db.query(User).filter(User.id.in_(user_ids)).all()
        else:
            # Get users who might be interested based on preferences
            users = await self._get_interested_users_for_festival(festival)

        notified_users = []

        for user in users:
            # Check user's notification preferences
            if await self._should_notify_user(
                user.id, NotificationType.FESTIVAL_ANNOUNCEMENT
            ):
                notification = Notification(
                    id=f"festival_{festival_id}_{user.id}_{datetime.utcnow().timestamp()}",
                    user_id=str(user.id),
                    notification_type=NotificationType.FESTIVAL_ANNOUNCEMENT,
                    title=f"New Festival: {festival.name}",
                    message=f"A new festival '{festival.name}' has been announced in {festival.location}!",
                    data={
                        "festival_id": str(festival.id),
                        "festival_name": festival.name,
                        "location": festival.location,
                        "dates": [date.isoformat() for date in festival.dates],
                        "artists": festival.artists[:5],  # Show first 5 artists
                    },
                    created_at=datetime.utcnow(),
                )

                await self._send_notification(notification, user)
                notified_users.append(str(user.id))

        return notified_users

    async def send_artist_lineup_notification(
        self,
        festival_id: str,
        new_artists: List[str],
        user_ids: Optional[List[str]] = None,
    ) -> List[str]:
        """
        Send notifications about artist lineup updates.

        Args:
            festival_id: Festival with updated lineup
            new_artists: List of newly added artists
            user_ids: Specific users to notify

        Returns:
            List of user IDs that were notified
        """
        festival = self.db.query(Festival).filter(Festival.id == festival_id).first()
        if not festival:
            raise ValueError(f"Festival {festival_id} not found")

        # Get users to notify
        if user_ids:
            users = self.db.query(User).filter(User.id.in_(user_ids)).all()
        else:
            # Get users who follow any of the new artists or are interested in the festival
            users = await self._get_users_following_artists(new_artists)

        notified_users = []

        for user in users:
            if await self._should_notify_user(
                user.id, NotificationType.ARTIST_LINEUP_UPDATE
            ):
                notification = Notification(
                    id=f"lineup_{festival_id}_{user.id}_{datetime.utcnow().timestamp()}",
                    user_id=str(user.id),
                    notification_type=NotificationType.ARTIST_LINEUP_UPDATE,
                    title=f"Lineup Update: {festival.name}",
                    message=f"New artists added to {festival.name}: {', '.join(new_artists[:3])}{'...' if len(new_artists) > 3 else ''}",
                    data={
                        "festival_id": str(festival.id),
                        "festival_name": festival.name,
                        "new_artists": new_artists,
                        "total_artists": len(festival.artists),
                    },
                    created_at=datetime.utcnow(),
                )

                await self._send_notification(notification, user)
                notified_users.append(str(user.id))

        return notified_users

    async def send_playlist_ready_notification(
        self, user_id: str, playlist_id: str
    ) -> bool:
        """
        Send notification when a playlist is ready.

        Args:
            user_id: User who requested the playlist
            playlist_id: Generated playlist ID

        Returns:
            True if notification was sent successfully
        """
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            return False

        from uuid import UUID
        user_uuid = UUID(user_id) if isinstance(user_id, str) else user_id
        if not await self._should_notify_user(user_uuid, NotificationType.PLAYLIST_READY):
            return False

        # Get playlist details (assuming playlist model exists)
        # For now, create a generic notification
        notification = Notification(
            id=f"playlist_{playlist_id}_{user_id}_{datetime.utcnow().timestamp()}",
            user_id=user_id,
            notification_type=NotificationType.PLAYLIST_READY,
            title="Your Playlist is Ready!",
            message="Your festival playlist has been generated and is ready to listen.",
            data={
                "playlist_id": playlist_id,
                "action_url": f"/playlists/{playlist_id}",
            },
            created_at=datetime.utcnow(),
        )

        return await self._send_notification(notification, user)

    async def send_recommendation_notification(
        self, user_id: str, recommendations: List[Dict[str, Any]]
    ) -> bool:
        """
        Send personalized recommendations to user.

        Args:
            user_id: User to send recommendations to
            recommendations: List of recommendation data

        Returns:
            True if notification was sent successfully
        """
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            return False

        if not await self._should_notify_user(user.id, NotificationType.RECOMMENDATION):
            return False

        notification = Notification(
            id=f"rec_{user_id}_{datetime.utcnow().timestamp()}",
            user_id=user_id,
            notification_type=NotificationType.RECOMMENDATION,
            title="New Recommendations for You",
            message=f"We found {len(recommendations)} festivals you might like!",
            data={"recommendations": recommendations, "action_url": "/recommendations"},
            created_at=datetime.utcnow(),
        )

        return await self._send_notification(notification, user)

    async def set_notification_preferences(
        self, user_id: str, preferences: Dict[str, Dict[str, Any]]
    ) -> bool:
        """
        Set user notification preferences.

        Args:
            user_id: User ID
            preferences: Dictionary of notification preferences

        Returns:
            True if preferences were saved successfully
        """
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            return False

        # Update user preferences in database
        if not user.preferences:
            user.preferences = {}

        user.preferences["notifications"] = preferences
        self.db.commit()

        return True

    async def get_notification_preferences(self, user_id: str) -> Dict[str, Any]:
        """Get user's notification preferences."""
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user or not user.preferences:
            return self._get_default_preferences()

        return dict(user.preferences.get("notifications", self._get_default_preferences()))

    async def _send_notification(self, notification: Notification, user: User) -> bool:
        """Send notification via email and/or push."""
        success = True

        preferences = await self.get_notification_preferences(str(user.id))
        notification_prefs = preferences.get(
            notification.notification_type.value,
            {"email_enabled": True, "push_enabled": True},
        )

        # Send email notification
        if notification_prefs.get("email_enabled", True):
            try:
                await self._send_email_notification(notification, user)
                notification.email_sent = True
            except Exception as e:
                print(f"Failed to send email notification: {e}")
                success = False

        # Send push notification
        if notification_prefs.get("push_enabled", True):
            try:
                await self._send_push_notification(notification, user)
                notification.push_sent = True
            except Exception as e:
                print(f"Failed to send push notification: {e}")
                success = False

        notification.sent_at = datetime.utcnow()
        return success

    async def _send_email_notification(self, notification: Notification, user: User) -> None:
        """Send email notification."""
        msg = MIMEMultipart()
        msg["From"] = self.from_email
        msg["To"] = user.email
        msg["Subject"] = notification.title

        # Create HTML email body
        html_body = f"""
        <html>
        <body>
            <h2>{notification.title}</h2>
            <p>{notification.message}</p>
            
            {self._format_notification_data(notification)}
            
            <p>
                <a href="https://festivalplaylist.com{notification.data.get('action_url', '')}" 
                   style="background-color: #4CAF50; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">
                    View Details
                </a>
            </p>
            
            <hr>
            <p><small>You can manage your notification preferences in your account settings.</small></p>
        </body>
        </html>
        """

        msg.attach(MIMEText(html_body, "html"))

        # Send email
        if self.smtp_username and self.smtp_password:
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_username, self.smtp_password)
                server.send_message(msg)

    async def _send_push_notification(self, notification: Notification, user: User) -> None:
        """Send web push notification."""
        # This would integrate with a push notification service like Firebase
        # For now, just log the notification
        push_payload = {
            "title": notification.title,
            "body": notification.message,
            "data": notification.data,
            "timestamp": notification.created_at.isoformat(),
        }

        print(
            f"Push notification for user {user.id}: {json.dumps(push_payload, indent=2)}"
        )
        # TODO: Implement actual push notification sending

    def _format_notification_data(self, notification: Notification) -> str:
        """Format notification data for email display."""
        if notification.notification_type == NotificationType.FESTIVAL_ANNOUNCEMENT:
            data = notification.data
            return f"""
            <div style="background-color: #f5f5f5; padding: 15px; margin: 10px 0; border-radius: 5px;">
                <h3>{data.get('festival_name')}</h3>
                <p><strong>Location:</strong> {data.get('location')}</p>
                <p><strong>Dates:</strong> {', '.join(data.get('dates', []))}</p>
                <p><strong>Featured Artists:</strong> {', '.join(data.get('artists', []))}</p>
            </div>
            """
        elif notification.notification_type == NotificationType.ARTIST_LINEUP_UPDATE:
            data = notification.data
            return f"""
            <div style="background-color: #e8f4fd; padding: 15px; margin: 10px 0; border-radius: 5px;">
                <h3>{data.get('festival_name')}</h3>
                <p><strong>New Artists:</strong> {', '.join(data.get('new_artists', []))}</p>
                <p><strong>Total Artists:</strong> {data.get('total_artists')}</p>
            </div>
            """
        return ""

    async def _should_notify_user(
        self, user_id: UUID, notification_type: NotificationType
    ) -> bool:
        """Check if user should receive this type of notification."""
        preferences = await self.get_notification_preferences(str(user_id))
        type_prefs = preferences.get(notification_type.value, {})

        # Check if notifications are enabled for this type
        if not (
            type_prefs.get("email_enabled", True)
            or type_prefs.get("push_enabled", True)
        ):
            return False

        # Check frequency limits
        frequency = type_prefs.get("frequency", NotificationFrequency.IMMEDIATE.value)
        if frequency != NotificationFrequency.IMMEDIATE.value:
            # TODO: Implement frequency checking logic
            pass

        return True

    async def _get_interested_users_for_festival(
        self, festival: Festival
    ) -> List[User]:
        """Get users who might be interested in a festival based on their preferences."""
        # This would use the recommendation engine to find users with similar taste
        # For now, return all users (in a real implementation, this would be more sophisticated)
        return self.db.query(User).limit(100).all()

    async def _get_users_following_artists(self, artists: List[str]) -> List[User]:
        """Get users who follow any of the specified artists."""
        # This would query user preferences to find users interested in these artists
        # For now, return all users
        return self.db.query(User).limit(100).all()

    def _get_default_preferences(self) -> Dict[str, Any]:
        """Get default notification preferences."""
        return {
            NotificationType.FESTIVAL_ANNOUNCEMENT.value: {
                "email_enabled": True,
                "push_enabled": True,
                "frequency": NotificationFrequency.IMMEDIATE.value,
            },
            NotificationType.ARTIST_LINEUP_UPDATE.value: {
                "email_enabled": True,
                "push_enabled": True,
                "frequency": NotificationFrequency.DAILY.value,
            },
            NotificationType.PLAYLIST_READY.value: {
                "email_enabled": True,
                "push_enabled": True,
                "frequency": NotificationFrequency.IMMEDIATE.value,
            },
            NotificationType.RECOMMENDATION.value: {
                "email_enabled": True,
                "push_enabled": False,
                "frequency": NotificationFrequency.WEEKLY.value,
            },
        }
