#!/bin/bash
# SSL Certificate Setup Script
# Automatically configures SSL certificates based on environment

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
SSL_DIR="$PROJECT_ROOT/ssl"
ENV_FILE="$PROJECT_ROOT/.env"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}🔒 SSL Certificate Setup${NC}"
echo "=========================="
echo

# Load environment variables
if [ -f "$ENV_FILE" ]; then
    export $(grep -v '^#' "$ENV_FILE" | xargs)
fi

# Determine if we're using a domain or localhost
DOMAIN="${DOMAIN_NAME:-}"
CERTBOT_EMAIL="${CERTBOT_EMAIL:-}"

if [ -z "$DOMAIN" ] || [ "$DOMAIN" = "localhost" ] || [ "$DOMAIN" = "127.0.0.1" ]; then
    echo -e "${YELLOW}📍 No domain configured - setting up for localhost${NC}"
    SETUP_TYPE="localhost"
else
    echo -e "${GREEN}🌐 Domain configured: $DOMAIN${NC}"
    SETUP_TYPE="domain"
fi

# Create SSL directory
mkdir -p "$SSL_DIR"

# Function to generate self-signed certificate for localhost
generate_self_signed() {
    echo
    echo -e "${BLUE}Generating self-signed SSL certificate for localhost...${NC}"
    
    CERT_FILE="$SSL_DIR/localhost.crt"
    KEY_FILE="$SSL_DIR/localhost.key"
    
    if [ -f "$CERT_FILE" ] && [ -f "$KEY_FILE" ]; then
        echo -e "${YELLOW}⚠️  Certificate already exists${NC}"
        read -p "Regenerate? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo -e "${GREEN}✓ Using existing certificate${NC}"
            return 0
        fi
        rm -f "$CERT_FILE" "$KEY_FILE"
    fi
    
    # Generate certificate
    openssl req -x509 -newkey rsa:4096 -nodes \
        -keyout "$KEY_FILE" \
        -out "$CERT_FILE" \
        -days 365 \
        -subj "/C=US/ST=State/L=City/O=FestivalPlaylistGenerator/CN=localhost" \
        -addext "subjectAltName=DNS:localhost,DNS:*.localhost,IP:127.0.0.1" \
        2>/dev/null
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Self-signed certificate generated successfully!${NC}"
        echo "  Certificate: $CERT_FILE"
        echo "  Private Key: $KEY_FILE"
        echo
        echo -e "${YELLOW}⚠️  Browser Security Warning:${NC}"
        echo "  Your browser will show a security warning because this is self-signed."
        echo "  This is normal for local development."
        echo "  Click 'Advanced' → 'Proceed to localhost' to continue."
        return 0
    else
        echo -e "${RED}✗ Failed to generate certificate${NC}"
        return 1
    fi
}

# Function to setup Let's Encrypt certificate
setup_letsencrypt() {
    echo
    echo -e "${BLUE}Setting up Let's Encrypt certificate for $DOMAIN...${NC}"
    
    # Check if certbot is installed
    if ! command -v certbot &> /dev/null; then
        echo -e "${YELLOW}⚠️  Certbot not found. Installing...${NC}"
        
        # Detect OS and install certbot
        if [[ "$OSTYPE" == "linux-gnu"* ]]; then
            if command -v apt-get &> /dev/null; then
                sudo apt-get update
                sudo apt-get install -y certbot
            elif command -v yum &> /dev/null; then
                sudo yum install -y certbot
            else
                echo -e "${RED}✗ Unable to install certbot automatically${NC}"
                echo "Please install certbot manually: https://certbot.eff.org/"
                return 1
            fi
        elif [[ "$OSTYPE" == "darwin"* ]]; then
            if command -v brew &> /dev/null; then
                brew install certbot
            else
                echo -e "${RED}✗ Homebrew not found. Please install certbot manually${NC}"
                echo "Visit: https://certbot.eff.org/"
                return 1
            fi
        else
            echo -e "${RED}✗ Unsupported OS for automatic certbot installation${NC}"
            echo "Please install certbot manually: https://certbot.eff.org/"
            return 1
        fi
    fi
    
    # Validate email
    if [ -z "$CERTBOT_EMAIL" ]; then
        echo -e "${YELLOW}⚠️  No email configured for Let's Encrypt notifications${NC}"
        read -p "Enter email address: " CERTBOT_EMAIL
        
        if [ -z "$CERTBOT_EMAIL" ]; then
            echo -e "${RED}✗ Email is required for Let's Encrypt${NC}"
            return 1
        fi
        
        # Update .env file
        if grep -q "^CERTBOT_EMAIL=" "$ENV_FILE"; then
            sed -i.bak "s|^CERTBOT_EMAIL=.*|CERTBOT_EMAIL=$CERTBOT_EMAIL|" "$ENV_FILE"
        else
            echo "CERTBOT_EMAIL=$CERTBOT_EMAIL" >> "$ENV_FILE"
        fi
    fi
    
    echo
    echo -e "${BLUE}📋 Certificate Request Details:${NC}"
    echo "  Domain: $DOMAIN"
    echo "  Email: $CERTBOT_EMAIL"
    echo "  Method: Standalone (requires port 80)"
    echo
    echo -e "${YELLOW}⚠️  Important:${NC}"
    echo "  1. Port 80 must be available (stop any web servers)"
    echo "  2. Domain must point to this server's IP"
    echo "  3. Firewall must allow incoming port 80"
    echo
    read -p "Continue? (y/N): " -n 1 -r
    echo
    
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Cancelled."
        return 1
    fi
    
    # Request certificate using standalone mode
    echo
    echo -e "${BLUE}Requesting certificate from Let's Encrypt...${NC}"
    
    sudo certbot certonly \
        --standalone \
        --non-interactive \
        --agree-tos \
        --email "$CERTBOT_EMAIL" \
        -d "$DOMAIN"
    
    if [ $? -eq 0 ]; then
        # Copy certificates to our SSL directory
        LETSENCRYPT_DIR="/etc/letsencrypt/live/$DOMAIN"
        
        sudo cp "$LETSENCRYPT_DIR/fullchain.pem" "$SSL_DIR/$DOMAIN.crt"
        sudo cp "$LETSENCRYPT_DIR/privkey.pem" "$SSL_DIR/$DOMAIN.key"
        sudo chown $(whoami):$(whoami) "$SSL_DIR/$DOMAIN.crt" "$SSL_DIR/$DOMAIN.key"
        
        echo -e "${GREEN}✓ Let's Encrypt certificate obtained successfully!${NC}"
        echo "  Certificate: $SSL_DIR/$DOMAIN.crt"
        echo "  Private Key: $SSL_DIR/$DOMAIN.key"
        echo
        echo -e "${BLUE}📝 Certificate Renewal:${NC}"
        echo "  Certificates expire in 90 days."
        echo "  Set up auto-renewal with: sudo certbot renew --dry-run"
        echo "  Add to crontab: 0 0 * * * certbot renew --quiet"
        
        # Update .env file with certificate paths
        if grep -q "^SSL_CERT_PATH=" "$ENV_FILE"; then
            sed -i.bak "s|^SSL_CERT_PATH=.*|SSL_CERT_PATH=ssl/$DOMAIN.crt|" "$ENV_FILE"
        else
            echo "SSL_CERT_PATH=ssl/$DOMAIN.crt" >> "$ENV_FILE"
        fi
        
        if grep -q "^SSL_KEY_PATH=" "$ENV_FILE"; then
            sed -i.bak "s|^SSL_KEY_PATH=.*|SSL_KEY_PATH=ssl/$DOMAIN.key|" "$ENV_FILE"
        else
            echo "SSL_KEY_PATH=ssl/$DOMAIN.key" >> "$ENV_FILE"
        fi
        
        return 0
    else
        echo -e "${RED}✗ Failed to obtain Let's Encrypt certificate${NC}"
        echo
        echo -e "${YELLOW}💡 Troubleshooting:${NC}"
        echo "  1. Ensure domain DNS points to this server"
        echo "  2. Check firewall allows port 80"
        echo "  3. Stop any services using port 80"
        echo "  4. Try manual mode: sudo certbot certonly --manual -d $DOMAIN"
        return 1
    fi
}

# Function to update .env file
update_env_file() {
    local use_https="$1"
    local redirect_uri="$2"
    
    echo
    echo -e "${BLUE}Updating .env configuration...${NC}"
    
    # Update USE_HTTPS
    if grep -q "^USE_HTTPS=" "$ENV_FILE"; then
        sed -i.bak "s|^USE_HTTPS=.*|USE_HTTPS=$use_https|" "$ENV_FILE"
    else
        echo "USE_HTTPS=$use_https" >> "$ENV_FILE"
    fi
    
    # Update OAUTH_REDIRECT_URI
    if grep -q "^OAUTH_REDIRECT_URI=" "$ENV_FILE"; then
        sed -i.bak "s|^OAUTH_REDIRECT_URI=.*|OAUTH_REDIRECT_URI=$redirect_uri|" "$ENV_FILE"
    else
        echo "OAUTH_REDIRECT_URI=$redirect_uri" >> "$ENV_FILE"
    fi
    
    echo -e "${GREEN}✓ Configuration updated${NC}"
}

# Main setup logic
case "$SETUP_TYPE" in
    localhost)
        if generate_self_signed; then
            update_env_file "True" "https://localhost:8000/auth/callback"
            echo
            echo -e "${GREEN}✓ SSL setup complete for localhost!${NC}"
            echo
            echo -e "${BLUE}Next steps:${NC}"
            echo "  1. Restart the application: ./festival.sh restart"
            echo "  2. Access via: https://localhost:8000"
            echo "  3. Accept the browser security warning"
            echo
            echo -e "${YELLOW}📝 Update OAuth Provider Settings:${NC}"
            echo "  Update redirect URIs in your OAuth provider dashboards:"
            echo "  • Google: https://console.cloud.google.com/apis/credentials"
            echo "  • Spotify: https://developer.spotify.com/dashboard"
            echo "  New redirect URI: https://localhost:8000/auth/callback"
        else
            exit 1
        fi
        ;;
    domain)
        if setup_letsencrypt; then
            update_env_file "True" "https://$DOMAIN/auth/callback"
            echo
            echo -e "${GREEN}✓ SSL setup complete for $DOMAIN!${NC}"
            echo
            echo -e "${BLUE}Next steps:${NC}"
            echo "  1. Restart the application: ./festival.sh restart"
            echo "  2. Access via: https://$DOMAIN"
            echo
            echo -e "${YELLOW}📝 Update OAuth Provider Settings:${NC}"
            echo "  Update redirect URIs in your OAuth provider dashboards:"
            echo "  • Google: https://console.cloud.google.com/apis/credentials"
            echo "  • Spotify: https://developer.spotify.com/dashboard"
            echo "  New redirect URI: https://$DOMAIN/auth/callback"
        else
            echo
            echo -e "${YELLOW}💡 Fallback: Using self-signed certificate${NC}"
            if generate_self_signed; then
                update_env_file "True" "https://localhost:8000/auth/callback"
                echo -e "${GREEN}✓ Self-signed certificate ready${NC}"
            else
                exit 1
            fi
        fi
        ;;
esac

echo
echo -e "${GREEN}🎉 SSL setup complete!${NC}"
