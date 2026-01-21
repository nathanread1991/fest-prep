"""Helper functions for converting external image URLs to use the nginx image cache proxy."""

from urllib.parse import quote
from typing import Optional, Dict, List, Any
from festival_playlist_generator.core.config import settings


def convert_to_proxy_url(image_url: Optional[str]) -> Optional[str]:
    """
    Convert external image URL to use local nginx proxy cache.
    
    Args:
        image_url: Original external image URL (e.g., from Spotify CDN)
    
    Returns:
        Proxy URL that routes through nginx cache, or None if image_url is None
        
    Examples:
        >>> convert_to_proxy_url("https://i.scdn.co/image/abc123")
        "http://localhost:80/images/proxy?url=https%3A%2F%2Fi.scdn.co%2Fimage%2Fabc123"
        
        >>> convert_to_proxy_url(None)
        None
    """
    # Return None for empty URLs
    if not image_url:
        return None
    
    # Check if caching is disabled
    if not settings.IMAGE_CACHE_ENABLED:
        return image_url
    
    # Don't convert if already a proxy URL
    if '/images/proxy' in image_url:
        return image_url
    
    # Don't convert relative URLs or data URLs
    if not image_url.startswith('http'):
        return image_url
    
    # URL-encode the image URL for safe query parameter
    # Keep :// and / unencoded so nginx can parse it correctly
    encoded_url = quote(image_url, safe=':/')
    
    # Build proxy URL
    proxy_base = settings.IMAGE_PROXY_URL.rstrip('/')
    return f"{proxy_base}/images/proxy?url={encoded_url}"


def convert_artist_images(artist: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert all image URLs in artist data to proxy URLs.
    
    Args:
        artist: Artist dictionary with image URL fields
        
    Returns:
        Artist dictionary with converted proxy URLs
    """
    if not artist:
        return artist
    
    # Convert Spotify image URL
    if 'spotify_image_url' in artist and artist['spotify_image_url']:
        artist['spotify_image_url'] = convert_to_proxy_url(artist['spotify_image_url'])
    
    # Convert logo URL
    if 'logo_url' in artist and artist['logo_url']:
        artist['logo_url'] = convert_to_proxy_url(artist['logo_url'])
    
    return artist


def convert_festival_images(festival: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert all image URLs in festival data to proxy URLs.
    
    Args:
        festival: Festival dictionary with image URL fields
        
    Returns:
        Festival dictionary with converted proxy URLs
    """
    if not festival:
        return festival
    
    # Convert festival logo URL
    if 'logo_url' in festival and festival['logo_url']:
        festival['logo_url'] = convert_to_proxy_url(festival['logo_url'])
    
    return festival


def convert_track_images(tracks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Convert album artwork URLs in track list to proxy URLs.
    
    Args:
        tracks: List of track dictionaries with album image fields
        
    Returns:
        List of tracks with converted proxy URLs
    """
    if not tracks:
        return tracks
    
    for track in tracks:
        # Convert album image URL
        if 'album_image' in track and track['album_image']:
            track['album_image'] = convert_to_proxy_url(track['album_image'])
        
        # Also handle nested album object structure
        if 'album' in track and isinstance(track['album'], dict):
            if 'images' in track['album'] and isinstance(track['album']['images'], list):
                for image in track['album']['images']:
                    if 'url' in image and image['url']:
                        image['url'] = convert_to_proxy_url(image['url'])
    
    return tracks


def convert_artist_list_images(artists: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Convert image URLs for a list of artists.
    
    Args:
        artists: List of artist dictionaries
        
    Returns:
        List of artists with converted proxy URLs
    """
    if not artists:
        return artists
    
    return [convert_artist_images(artist) for artist in artists]


def convert_festival_list_images(festivals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Convert image URLs for a list of festivals.
    
    Args:
        festivals: List of festival dictionaries
        
    Returns:
        List of festivals with converted proxy URLs
    """
    if not festivals:
        return festivals
    
    return [convert_festival_images(festival) for festival in festivals]
