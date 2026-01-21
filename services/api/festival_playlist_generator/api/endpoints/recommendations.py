"""Recommendation API endpoints."""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from festival_playlist_generator.api.versioning import version_compatible_response
from festival_playlist_generator.core.database import get_db
from festival_playlist_generator.services.recommendation_engine import (
    ArtistRecommendation,
    FestivalRecommendation,
    RecommendationEngine,
    UserProfile,
)

router = APIRouter()


@router.get("/users/{user_id}/profile")
async def get_user_profile(
    user_id: str, request: Request, db: Session = Depends(get_db)
):
    """Get user's music preference profile."""
    try:
        engine = RecommendationEngine(db)
        profile = await engine.analyze_user_preferences(user_id)

        profile_data = {
            "user_id": profile.user_id,
            "preferred_genres": profile.preferred_genres,
            "preferred_artists": profile.preferred_artists,
            "known_songs_count": profile.known_songs_count,
            "total_songs_count": profile.total_songs_count,
            "discovery_rate": profile.discovery_rate,
            "created_at": profile.created_at.isoformat(),
        }

        return JSONResponse(
            content=version_compatible_response(
                request, profile_data, "User profile retrieved successfully"
            ),
            status_code=200,
        )

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get user profile: {str(e)}"
        )


@router.get("/users/{user_id}/festivals")
async def get_festival_recommendations(
    user_id: str, request: Request, limit: int = 10, db: Session = Depends(get_db)
):
    """Get personalized festival recommendations for a user."""
    try:
        engine = RecommendationEngine(db)
        recommendations = await engine.recommend_festivals(user_id, limit)

        recommendations_data = []
        for rec in recommendations:
            recommendations_data.append(
                {
                    "festival_id": rec.festival_id,
                    "festival_name": rec.festival_name,
                    "similarity_score": rec.similarity_score,
                    "matching_artists": rec.matching_artists,
                    "recommended_artists": rec.recommended_artists,
                    "dates": [date.isoformat() for date in rec.dates],
                    "location": rec.location,
                }
            )

        return JSONResponse(
            content=version_compatible_response(
                request,
                {
                    "recommendations": recommendations_data,
                    "total_count": len(recommendations_data),
                },
                f"Found {len(recommendations_data)} festival recommendations",
            ),
            status_code=200,
        )

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get festival recommendations: {str(e)}"
        )


@router.get("/festivals/{festival_id}/artists/recommendations")
async def get_artist_recommendations(
    festival_id: str,
    user_id: str,
    request: Request,
    limit: int = 10,
    db: Session = Depends(get_db),
):
    """Get personalized artist recommendations from a festival lineup."""
    try:
        engine = RecommendationEngine(db)
        recommendations = await engine.recommend_artists(festival_id, user_id, limit)

        recommendations_data = []
        for rec in recommendations:
            recommendations_data.append(
                {
                    "artist_id": rec.artist_id,
                    "artist_name": rec.artist_name,
                    "similarity_score": rec.similarity_score,
                    "genres": rec.genres,
                    "popularity_score": rec.popularity_score,
                }
            )

        return JSONResponse(
            content=version_compatible_response(
                request,
                {
                    "recommendations": recommendations_data,
                    "total_count": len(recommendations_data),
                    "festival_id": festival_id,
                },
                f"Found {len(recommendations_data)} artist recommendations",
            ),
            status_code=200,
        )

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get artist recommendations: {str(e)}"
        )


@router.post("/users/{user_id}/similarity")
async def calculate_similarity_scores(
    user_id: str, items: List[dict], request: Request, db: Session = Depends(get_db)
):
    """Calculate similarity scores between user profile and provided items."""
    try:
        engine = RecommendationEngine(db)
        profile = await engine.analyze_user_preferences(user_id)

        # Convert dict items to objects with required attributes
        class Item:
            def __init__(self, item_dict):
                self.id = item_dict.get("id")
                self.genres = item_dict.get("genres", [])

        item_objects = [Item(item) for item in items]
        scores = await engine.calculate_similarity_scores(profile, item_objects)

        return JSONResponse(
            content=version_compatible_response(
                request,
                {"similarity_scores": scores, "user_id": user_id},
                "Similarity scores calculated successfully",
            ),
            status_code=200,
        )

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to calculate similarity scores: {str(e)}"
        )
