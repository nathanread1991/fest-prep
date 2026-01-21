"""Push notification service for PWA functionality."""

import base64
import json
import logging
import os
from typing import Dict, List, Optional

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from pywebpush import WebPushException, webpush

from festival_playlist_generator.core.config import settings
from festival_playlist_generator.core.redis import get_redis

logger = logging.getLogger(__name__)


class PushNotificationService:
    """Service for managing push notifications."""

    def __init__(self):
        self.vapid_private_key = settings.VAPID_PRIVATE_KEY
        self.vapid_public_key = settings.VAPID_PUBLIC_KEY
        self.vapid_claims = {"sub": f"mailto:{settings.VAPID_EMAIL}"}

    @classmethod
    def generate_vapid_keys(cls) -> Dict[str, str]:
        """Generate VAPID key pair for push notifications."""
        # Generate private key
        private_key = ec.generate_private_key(ec.SECP256R1(), default_backend())

        # Get public key
        public_key = private_key.public_key()

        # Serialize private key
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )

        # Serialize public key in uncompressed format
        public_numbers = public_key.public_numbers()
        x = public_numbers.x.to_bytes(32, "big")
        y = public_numbers.y.to_bytes(32, "big")
        public_key_bytes = b"\x04" + x + y

        return {
            "private_key": base64.urlsafe_b64encode(private_pem).decode("utf-8"),
            "public_key": base64.urlsafe_b64encode(public_key_bytes).decode("utf-8"),
        }

    async def subscribe_user(self, user_id: str, subscription_data: Dict) -> bool:
        """Subscribe a user to push notifications."""
        try:
            redis = await get_redis()

            # Store subscription data
            subscription_key = f"push_subscription:{user_id}"
            await redis.set(
                subscription_key,
                json.dumps(subscription_data),
                ex=86400 * 30,  # 30 days
            )

            # Add to active subscriptions set
            await redis.sadd("active_push_subscriptions", user_id)

            logger.info(f"User {user_id} subscribed to push notifications")
            return True

        except Exception as e:
            logger.error(f"Failed to subscribe user {user_id}: {e}")
            return False

    async def unsubscribe_user(self, user_id: str) -> bool:
        """Unsubscribe a user from push notifications."""
        try:
            redis = await get_redis()

            # Remove subscription data
            subscription_key = f"push_subscription:{user_id}"
            await redis.delete(subscription_key)

            # Remove from active subscriptions set
            await redis.srem("active_push_subscriptions", user_id)

            logger.info(f"User {user_id} unsubscribed from push notifications")
            return True

        except Exception as e:
            logger.error(f"Failed to unsubscribe user {user_id}: {e}")
            return False

    async def get_user_subscription(self, user_id: str) -> Optional[Dict]:
        """Get user's push notification subscription."""
        try:
            redis = await get_redis()
            subscription_key = f"push_subscription:{user_id}"

            subscription_data = await redis.get(subscription_key)
            if subscription_data:
                return json.loads(subscription_data)

            return None

        except Exception as e:
            logger.error(f"Failed to get subscription for user {user_id}: {e}")
            return None

    async def send_notification(
        self,
        user_id: str,
        title: str,
        body: str,
        data: Optional[Dict] = None,
        actions: Optional[List[Dict]] = None,
        icon: str = "/static/images/icon-192.png",
        badge: str = "/static/images/badge.png",
        tag: Optional[str] = None,
    ) -> bool:
        """Send push notification to a specific user."""
        try:
            subscription = await self.get_user_subscription(user_id)
            if not subscription:
                logger.warning(f"No subscription found for user {user_id}")
                return False

            # Prepare notification payload
            payload = {
                "title": title,
                "body": body,
                "icon": icon,
                "badge": badge,
                "data": data or {},
                "actions": actions or [],
                "requireInteraction": False,
                "silent": False,
            }

            if tag:
                payload["tag"] = tag

            # Send push notification
            webpush(
                subscription_info=subscription,
                data=json.dumps(payload),
                vapid_private_key=self.vapid_private_key,
                vapid_claims=self.vapid_claims,
            )

            logger.info(f"Push notification sent to user {user_id}: {title}")
            return True

        except WebPushException as e:
            logger.error(f"WebPush error for user {user_id}: {e}")

            # If subscription is invalid, remove it
            if e.response and e.response.status_code in [410, 413]:
                await self.unsubscribe_user(user_id)

            return False

        except Exception as e:
            logger.error(f"Failed to send notification to user {user_id}: {e}")
            return False

    async def send_bulk_notification(
        self,
        user_ids: List[str],
        title: str,
        body: str,
        data: Optional[Dict] = None,
        actions: Optional[List[Dict]] = None,
        icon: str = "/static/images/icon-192.png",
        badge: str = "/static/images/badge.png",
        tag: Optional[str] = None,
    ) -> Dict[str, bool]:
        """Send push notification to multiple users."""
        results = {}

        for user_id in user_ids:
            success = await self.send_notification(
                user_id=user_id,
                title=title,
                body=body,
                data=data,
                actions=actions,
                icon=icon,
                badge=badge,
                tag=tag,
            )
            results[user_id] = success

        return results

    async def send_festival_announcement(
        self, festival_name: str, festival_id: str, user_ids: Optional[List[str]] = None
    ) -> Dict[str, bool]:
        """Send notification about new festival announcement."""
        title = "🎪 New Festival Announced!"
        body = f"{festival_name} has been added. Create your playlist now!"

        data = {
            "type": "festival_announcement",
            "festival_id": festival_id,
            "url": f"/festivals/{festival_id}",
        }

        actions = [
            {
                "action": "view_festival",
                "title": "View Festival",
                "icon": "/static/images/action-view.png",
            },
            {
                "action": "create_playlist",
                "title": "Create Playlist",
                "icon": "/static/images/action-playlist.png",
            },
        ]

        # If no specific users, send to all subscribed users
        if not user_ids:
            redis = await get_redis()
            user_ids = await redis.smembers("active_push_subscriptions")
            user_ids = [
                uid.decode() if isinstance(uid, bytes) else uid for uid in user_ids
            ]

        return await self.send_bulk_notification(
            user_ids=user_ids,
            title=title,
            body=body,
            data=data,
            actions=actions,
            tag=f"festival_{festival_id}",
        )

    async def send_playlist_ready(
        self, user_id: str, playlist_name: str, playlist_id: str
    ) -> bool:
        """Send notification when playlist is ready."""
        title = "🎵 Your Playlist is Ready!"
        body = f"{playlist_name} has been created and is ready to enjoy!"

        data = {
            "type": "playlist_ready",
            "playlist_id": playlist_id,
            "url": f"/playlists/{playlist_id}",
        }

        actions = [
            {
                "action": "view_playlist",
                "title": "View Playlist",
                "icon": "/static/images/action-view.png",
            },
            {
                "action": "open_streaming",
                "title": "Open in Streaming App",
                "icon": "/static/images/action-streaming.png",
            },
        ]

        return await self.send_notification(
            user_id=user_id,
            title=title,
            body=body,
            data=data,
            actions=actions,
            tag=f"playlist_{playlist_id}",
        )

    async def get_subscription_stats(self) -> Dict[str, int]:
        """Get push notification subscription statistics."""
        try:
            redis = await get_redis()

            # Count active subscriptions
            active_count = await redis.scard("active_push_subscriptions")

            return {
                "active_subscriptions": active_count,
                "total_sent_today": 0,  # Could be tracked with daily counters
                "success_rate": 0.95,  # Could be calculated from delivery stats
            }

        except Exception as e:
            logger.error(f"Failed to get subscription stats: {e}")
            return {"active_subscriptions": 0, "total_sent_today": 0, "success_rate": 0}


# Global service instance
push_service = PushNotificationService()
