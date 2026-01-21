# nginx Image Caching Setup

This directory contains the nginx configuration for caching external images (Spotify CDN, festival logos) to improve page load performance.

## Architecture

```
Browser Request
    ↓
nginx (port 80)
    ↓
    ├─ /images/proxy?url=... → Cache & Proxy to external URL
    └─ /* → Reverse proxy to FastAPI app (port 8000)
```

## Features

- **Automatic Caching**: Images cached for 30 days
- **Rate Limiting**: 100 requests/minute per IP
- **Domain Whitelist**: Only Spotify CDN domains allowed
- **Security**: 10MB file size limit, timeout protection
- **Performance**: < 10ms cache hits, 5GB cache size

## Configuration

### Cache Settings
- **Location**: `/var/cache/nginx/images`
- **Max Size**: 5GB
- **Expiry**: 30 days of inactivity
- **Memory**: 100MB for cache keys

### Whitelisted Domains
- `i.scdn.co` - Spotify CDN
- `mosaic.scdn.co` - Spotify mosaic images
- `lineup-images.scdn.co` - Spotify lineup images
- `image-cdn-ak.spotifycdn.com` - Spotify CDN alternate
- `image-cdn-fa.spotifycdn.com` - Spotify CDN alternate

### Rate Limiting
- **Limit**: 100 requests per minute per IP
- **Burst**: 20 additional requests allowed
- **Response**: 429 Too Many Requests on limit exceeded

## Usage

### Starting the Service

```bash
# Start all services including nginx
docker-compose up -d

# Check nginx is running
docker-compose ps nginx

# View nginx logs
docker-compose logs -f nginx
```

### Testing the Image Proxy

```bash
# Test with a Spotify image URL
curl "http://localhost:80/images/proxy?url=https://i.scdn.co/image/ab67616d0000b273..."

# Check cache status (should be MISS first time, HIT second time)
curl -I "http://localhost:80/images/proxy?url=https://i.scdn.co/image/ab67616d0000b273..."
```

### Monitoring

```bash
# Check cache size
docker exec festival_nginx du -sh /var/cache/nginx/images

# Count cached files
docker exec festival_nginx find /var/cache/nginx/images -type f | wc -l

# View cache directory
docker exec festival_nginx ls -lah /var/cache/nginx/images
```

### Clearing the Cache

```bash
# Clear all cached images
docker exec festival_nginx rm -rf /var/cache/nginx/images/*

# Reload nginx to recreate cache structure
docker-compose restart nginx
```

## Health Check

nginx includes a health check endpoint:

```bash
curl http://localhost:80/nginx-health
# Response: healthy
```

## Troubleshooting

### Images not caching
1. Check nginx logs: `docker-compose logs nginx`
2. Verify domain is whitelisted in `image-cache.conf`
3. Check cache directory permissions
4. Verify cache size hasn't exceeded 5GB limit

### 403 Forbidden errors
- Image URL domain is not in the whitelist
- Add domain to the whitelist in `image-cache.conf`

### 429 Too Many Requests
- Rate limit exceeded (100 req/min per IP)
- Wait a minute or increase limit in `image-cache.conf`

### Cache not persisting
- Check docker volume: `docker volume inspect festival_nginx_cache`
- Verify volume is mounted correctly in `docker-compose.yml`

## Configuration Files

- `image-cache.conf` - Main nginx configuration
- `Dockerfile` - nginx container build instructions
- `../docker-compose.yml` - Service orchestration

## Performance Metrics

Expected performance:
- **Cache Hit**: < 10ms response time
- **Cache Miss**: < 5s (download + cache)
- **Cache Hit Rate**: > 90% after initial page loads
- **Storage**: ~1-2GB for typical usage

## Security

- Only HTTPS URLs from whitelisted domains accepted
- 10MB file size limit prevents abuse
- 5-second timeout prevents hanging requests
- Rate limiting prevents DoS attacks
- No cookies or sensitive headers cached
