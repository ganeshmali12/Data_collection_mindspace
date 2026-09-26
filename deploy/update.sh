#!/usr/bin/env bash
# ==============================================================================
# MANOVEDH PLATFORM — 1-COMMAND UPDATE SCRIPT
# ==============================================================================
# Usage:
#   sudo bash deploy/update.sh
# ==============================================================================

set -e

# ANSI Color Codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

DEPLOY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${DEPLOY_DIR}/.." && pwd)"

cd "${ROOT_DIR}"

echo -e "${CYAN}${BOLD}"
echo "======================================================================"
echo "          UPDATING MANOVEDH APPLICATION TO LATEST VERSION             "
echo "======================================================================"
echo -e "${NC}"

# Check Docker Compose command
if docker compose version &> /dev/null; then
    DOCKER_COMPOSE="docker compose"
else
    DOCKER_COMPOSE="docker-compose"
fi

# 1. Pull latest code from git
echo -e "${YELLOW}[1/4] Pulling latest code from Git repository...${NC}"
git pull origin main || git pull || true
echo -e "${GREEN}✓ Code updated.${NC}"

# 2. Rebuild and restart containers
echo -e "${YELLOW}[2/4] Rebuilding Docker containers with updated code...${NC}"
${DOCKER_COMPOSE} -f "${ROOT_DIR}/docker-compose.yml" up --build -d
echo -e "${GREEN}✓ Containers restarted successfully.${NC}"

# 3. Run database migrations
echo -e "${YELLOW}[3/4] Checking and applying database migrations...${NC}"
docker exec mindspace-data-collection-web python manage.py migrate --noinput
echo -e "${GREEN}✓ Database migrations up to date.${NC}"

# 4. Collect static files
echo -e "${YELLOW}[4/4] Updating static assets...${NC}"
docker exec mindspace-data-collection-web python manage.py collectstatic --noinput
echo -e "${GREEN}✓ Static files collected.${NC}"

echo -e "${GREEN}${BOLD}"
echo "======================================================================"
echo "          ✓ APPLICATION SUCCESSFULLY UPDATED AND RUNNING!             "
echo "======================================================================"
echo -e "${NC}"
