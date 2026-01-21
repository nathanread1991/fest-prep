#!/bin/bash
# Generate self-signed SSL certificate for local development

CERT_DIR="ssl"
CERT_FILE="$CERT_DIR/localhost.crt"
KEY_FILE="$CERT_DIR/localhost.key"

# Create ssl directory if it doesn't exist
mkdir -p "$CERT_DIR"

# Check if certificate already exists
if [ -f "$CERT_FILE" ] && [ -f "$KEY_FILE" ]; then
    echo "SSL certificate already exists at $CERT_FILE"
    echo "To regenerate, delete the ssl directory and run this script again"
    exit 0
fi

echo "Generating self-signed SSL certificate for localhost..."

# Generate private key and certificate
openssl req -x509 -newkey rsa:4096 -nodes \
    -keyout "$KEY_FILE" \
    -out "$CERT_FILE" \
    -days 365 \
    -subj "/C=US/ST=State/L=City/O=Organization/CN=localhost" \
    -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"

if [ $? -eq 0 ]; then
    echo "✓ SSL certificate generated successfully!"
    echo "  Certificate: $CERT_FILE"
    echo "  Private Key: $KEY_FILE"
    echo ""
    echo "Note: Your browser will show a security warning because this is a self-signed certificate."
    echo "This is normal for local development. Click 'Advanced' and 'Proceed to localhost' to continue."
else
    echo "✗ Failed to generate SSL certificate"
    exit 1
fi
