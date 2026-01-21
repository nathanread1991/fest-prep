"""Push notification API endpoints."""

import logging
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from festival_playlist_generator.api.versioning import (
    get_request_version,
    version_compatible_response,
)
from festival_playlist_generator.core.config import settings
from festival_playlist_generator.services.push_notifications import push_service

logger = logging.getLogger(__name__)

router = APIRouter()


class PushSubscription(BaseModel):
    """Push notification subscription data."""

    endpoint: str
    keys: Dict[str, str]  # Contains 'p256dh' and 'auth' keys


class NotificationRequest(BaseModel):
    """Request to send a notification."""

    title: str
    body: str
    data: Optional[Dict] = None
    actions: Optional[List[Dict]] = None
    icon: Optional[str] = None
    badge: Optional[str] = None
    tag: Optional[str] = None


@router.get("/vapid-public-key")
async def get_vapid_public_key(request: Request):
    """Get VAPID public key for push notification subscription."""
    if not settings.VAPID_PUBLIC_KEY:
        raise HTTPException(status_code=503, detail="Push notifications not configured")

    return version_compatible_response(
        request,
        {"public_key": settings.VAPID_PUBLIC_KEY},
        "VAPID public key retrieved successfully",
    )


@router.post("/subscribe")
async def subscribe_to_notifications(
    subscription: PushSubscription,
    request: Request,
    user_id: str = "anonymous",  # In real app, get from auth
):
    """Subscribe to push notifications."""
    try:
        subscription_data = {
            "endpoint": subscription.endpoint,
            "keys": subscription.keys,
        }

        success = await push_service.subscribe_user(user_id, subscription_data)

        if success:
            return version_compatible_response(
                request,
                {"subscribed": True, "user_id": user_id},
                "Successfully subscribed to push notifications",
            )
        else:
            raise HTTPException(
                status_code=500, detail="Failed to subscribe to notifications"
            )

    except Exception as e:
        logger.error(f"Subscription error: {e}")
        raise HTTPException(status_code=500, detail="Failed to process subscription")


@router.post("/unsubscribe")
async def unsubscribe_from_notifications(
    request: Request, user_id: str = "anonymous"  # In real app, get from auth
):
    """Unsubscribe from push notifications."""
    try:
        success = await push_service.unsubscribe_user(user_id)

        if success:
            return version_compatible_response(
                request,
                {"unsubscribed": True, "user_id": user_id},
                "Successfully unsubscribed from push notifications",
            )
        else:
            raise HTTPException(
                status_code=500, detail="Failed to unsubscribe from notifications"
            )

    except Exception as e:
        logger.error(f"Unsubscription error: {e}")
        raise HTTPException(status_code=500, detail="Failed to process unsubscription")


@router.get("/subscription-status")
async def get_subscription_status(
    request: Request, user_id: str = "anonymous"  # In real app, get from auth
):
    """Get user's push notification subscription status."""
    try:
        subscription = await push_service.get_user_subscription(user_id)

        return version_compatible_response(
            request,
            {
                "subscribed": subscription is not None,
                "user_id": user_id,
                "subscription": subscription,
            },
            "Subscription status retrieved successfully",
        )

    except Exception as e:
        logger.error(f"Status check error: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to check subscription status"
        )


@router.post("/send-test")
async def send_test_notification(
    notification: NotificationRequest,
    request: Request,
    user_id: str = "anonymous",  # In real app, get from auth
):
    """Send a test notification (for development/testing)."""
    try:
        success = await push_service.send_notification(
            user_id=user_id,
            title=notification.title,
            body=notification.body,
            data=notification.data,
            actions=notification.actions,
            icon=notification.icon or "/static/images/icon-192.png",
            badge=notification.badge or "/static/images/badge.png",
            tag=notification.tag,
        )

        if success:
            return version_compatible_response(
                request,
                {"sent": True, "user_id": user_id},
                "Test notification sent successfully",
            )
        else:
            raise HTTPException(
                status_code=500, detail="Failed to send test notification"
            )

    except Exception as e:
        logger.error(f"Test notification error: {e}")
        raise HTTPException(status_code=500, detail="Failed to send test notification")


@router.get("/stats")
async def get_notification_stats(request: Request):
    """Get push notification statistics."""
    try:
        stats = await push_service.get_subscription_stats()

        return version_compatible_response(
            request, stats, "Notification statistics retrieved successfully"
        )

    except Exception as e:
        logger.error(f"Stats error: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to get notification statistics"
        )


@router.post("/generate-vapid-keys")
async def generate_vapid_keys(request: Request):
    """Generate new VAPID keys (admin only)."""
    # In production, this should require admin authentication
    try:
        keys = push_service.generate_vapid_keys()

        return version_compatible_response(
            request,
            keys,
            "VAPID keys generated successfully. Add these to your environment variables.",
        )

    except Exception as e:
        logger.error(f"VAPID key generation error: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate VAPID keys")
