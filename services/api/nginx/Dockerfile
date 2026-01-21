# nginx Dockerfile for Image Caching
FROM nginx:alpine

# Copy custom nginx configuration
COPY image-cache.conf /etc/nginx/conf.d/default.conf

# Create cache directory with proper permissions
RUN mkdir -p /var/cache/nginx/images && \
    chown -R nginx:nginx /var/cache/nginx/images && \
    chmod -R 755 /var/cache/nginx/images

# Create directory for nginx logs
RUN mkdir -p /var/log/nginx && \
    chown -R nginx:nginx /var/log/nginx

# Expose port 8080 for the image proxy
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://localhost:8080/nginx-health || exit 1

# Start nginx in foreground
CMD ["nginx", "-g", "daemon off;"]
