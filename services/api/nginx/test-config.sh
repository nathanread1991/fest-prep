#!/bin/bash
# Test nginx configuration syntax

echo "Testing nginx configuration..."

# Create a temporary config without the upstream reference for syntax testing
cat > /tmp/test-nginx.conf << 'EOF'
proxy_cache_path /tmp/nginx-test-cache 
    levels=1:2 
    keys_zone=image_cache:100m 
    max_size=5g 
    inactive=30d 
    use_temp_path=off;

limit_req_zone $binary_remote_addr zone=image_limit:10m rate=100r/m;

server {
    listen 8080;
    server_name localhost;

    proxy_buffer_size 128k;
    proxy_buffers 4 256k;
    proxy_busy_buffers_size 256k;

    location /images/proxy {
        limit_req zone=image_limit burst=20 nodelay;
        limit_req_status 429;

        set $image_url $arg_url;

        if ($image_url = "") {
            return 400 "URL parameter required";
        }

        set $valid_domain 0;
        
        if ($image_url ~* "^https?://(i\.scdn\.co|mosaic\.scdn\.co|lineup-images\.scdn\.co|image-cdn-ak\.spotifycdn\.com|image-cdn-fa\.spotifycdn\.com)/") {
            set $valid_domain 1;
        }

        if ($valid_domain = 0) {
            return 403 "Domain not whitelisted";
        }

        proxy_pass $image_url;
        
        proxy_cache image_cache;
        proxy_cache_key "$image_url";
        proxy_cache_valid 200 30d;
        proxy_cache_valid 404 1m;
        proxy_cache_use_stale error timeout updating http_500 http_502 http_503 http_504;
        proxy_cache_lock on;
        proxy_cache_lock_timeout 5s;

        proxy_connect_timeout 5s;
        proxy_read_timeout 5s;
        proxy_send_timeout 5s;

        proxy_set_header User-Agent "FestivalPlaylistGenerator/1.0";
        proxy_set_header Accept "*/*";
        proxy_set_header Host $proxy_host;
        proxy_set_header Connection "";
        
        add_header X-Cache-Status $upstream_cache_status always;
        add_header Cache-Control "public, max-age=31536000, immutable" always;
        add_header Access-Control-Allow-Origin "*" always;
        
        proxy_hide_header Set-Cookie;
        proxy_hide_header X-Powered-By;
        proxy_ignore_headers Set-Cookie;

        client_max_body_size 10m;
        proxy_intercept_errors off;
    }

    location /nginx-health {
        access_log off;
        return 200 "healthy\n";
        add_header Content-Type text/plain;
    }
}
EOF

# Test the configuration
docker run --rm -v /tmp/test-nginx.conf:/etc/nginx/conf.d/default.conf:ro nginx:alpine nginx -t

if [ $? -eq 0 ]; then
    echo "✅ nginx configuration is valid!"
else
    echo "❌ nginx configuration has errors"
    exit 1
fi

# Clean up
rm /tmp/test-nginx.conf

echo "Configuration test complete."
