#!/bin/bash
# Create Synology secrets via web API

SERVER_URL="http://192.168.1.224:8080"
SYNOLOGY_URL="https://192.168.1.52:5001/"
SYNOLOGY_USERNAME="Bludo"

if [ -z "$1" ]; then
    echo "Usage: $0 <password>"
    echo "Creating Synology secrets for user: $SYNOLOGY_USERNAME"
    echo "URL: $SYNOLOGY_URL"
    exit 1
fi

PASSWORD="$1"

echo "Creating Synology secrets on $SERVER_URL..."
echo "Username: $SYNOLOGY_USERNAME"
echo "URL: $SYNOLOGY_URL"
echo ""

# Create URL secret
curl -s -X POST "$SERVER_URL/secrets" \
  -d "name=Synology NAS URL" \
  -d "service_type=synology" \
  -d "key=url" \
  -d "value=$SYNOLOGY_URL" \
  -w "\nHTTP Status: %{http_code}\n" | grep -E "(HTTP Status|Created|Updated)" || echo "✓ Created: synology/url"

# Create username secret
curl -s -X POST "$SERVER_URL/secrets" \
  -d "name=Synology Username" \
  -d "service_type=synology" \
  -d "key=username" \
  -d "value=$SYNOLOGY_USERNAME" \
  -w "\nHTTP Status: %{http_code}\n" | grep -E "(HTTP Status|Created|Updated)" || echo "✓ Created: synology/username"

# Create password secret
curl -s -X POST "$SERVER_URL/secrets" \
  -d "name=Synology Password" \
  -d "service_type=synology" \
  -d "key=password" \
  -d "value=$PASSWORD" \
  -w "\nHTTP Status: %{http_code}\n" | grep -E "(HTTP Status|Created|Updated)" || echo "✓ Created: synology/password"

echo ""
echo "Done! Check the web interface at $SERVER_URL/secrets"
