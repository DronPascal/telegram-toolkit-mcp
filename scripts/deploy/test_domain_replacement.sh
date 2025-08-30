#!/bin/bash
# Test Domain Replacement Script
# This script tests the domain replacement functionality locally

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}🧪 Testing Domain Replacement${NC}"
echo -e "${BLUE}=============================${NC}"

# Test domain
TEST_DOMAIN="test-domain.com"
TEMP_FILE="/tmp/nginx_test.conf"

# Copy nginx.conf for testing
cp nginx.conf "$TEMP_FILE"

echo -e "${YELLOW}📋 Original nginx.conf:${NC}"
grep "server_name" nginx.conf

# Test replacement
echo -e "${YELLOW}🔧 Applying domain replacement...${NC}"
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    sed -i '' "s/YOUR_DOMAIN_PLACEHOLDER/$TEST_DOMAIN/g" "$TEMP_FILE"
else
    # Linux
    sed -i "s/YOUR_DOMAIN_PLACEHOLDER/$TEST_DOMAIN/g" "$TEMP_FILE"
fi

echo -e "${YELLOW}📋 Modified nginx.conf:${NC}"
grep "server_name" "$TEMP_FILE"

# Verify replacement
if grep -q "$TEST_DOMAIN" "$TEMP_FILE"; then
    echo -e "${GREEN}✅ Domain replacement test PASSED${NC}"
    echo -e "${GREEN}   YOUR_DOMAIN_PLACEHOLDER successfully replaced with $TEST_DOMAIN${NC}"
else
    echo -e "${RED}❌ Domain replacement test FAILED${NC}"
    echo -e "${RED}   Domain replacement did not work${NC}"
    exit 1
fi

# Check for remaining placeholders
if grep -q "YOUR_DOMAIN_PLACEHOLDER" "$TEMP_FILE"; then
    echo -e "${RED}❌ Found remaining YOUR_DOMAIN_PLACEHOLDER in file${NC}"
    exit 1
else
    echo -e "${GREEN}✅ No remaining placeholders found${NC}"
fi

# Cleanup
rm "$TEMP_FILE"

echo -e "${GREEN}🎉 All domain replacement tests passed!${NC}"
