#!/bin/bash
API_URL="https://maint.featsinnovations.in"

echo "=== Testing All Endpoints ==="

# 1. Registration
echo "1. Testing Registration..."
NEW_MOBILE="98$(shuf -i 10000000-99999999 -n 1)"
REG_RESPONSE=$(curl -s -w "HTTP_STATUS:%{http_code}" \
  -X POST "$API_URL/register" \
  -H "Content-Type: application/json" \
  -d "{\"name\":\"API Test\",\"mobile\":\"$NEW_MOBILE\",\"password\":\"test123\"}")

REG_STATUS=${REG_RESPONSE##*HTTP_STATUS:}
echo "  Status: $REG_STATUS"

# 2. Login
echo -e "\n2. Testing Login..."
LOGIN_RESPONSE=$(curl -s -w "HTTP_STATUS:%{http_code}" \
  -X POST "$API_URL/login" \
  -H "Content-Type: application/json" \
  -d "{\"mobile\":\"$NEW_MOBILE\",\"password\":\"test123\"}")

LOGIN_STATUS=${LOGIN_RESPONSE##*HTTP_STATUS:}
echo "  Status: $LOGIN_STATUS"

# 3. GET endpoints
echo -e "\n3. Testing GET endpoints:"
for endpoint in get_building get_my_units; do
    STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X GET "$API_URL/$endpoint")
    echo "  $endpoint: $STATUS"
done

# 4. OPTIONS (CORS)
echo -e "\n4. Testing CORS..."
CORS_STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X OPTIONS "$API_URL/register")
echo "  CORS: $CORS_STATUS"

echo -e "\n✅ Testing Complete!"
