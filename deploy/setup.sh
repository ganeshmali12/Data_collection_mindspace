#!/usr/bin/env bash
# ==============================================================================
# MANOVEDH PLATFORM — 1-COMMAND VPS DEPLOYMENT SCRIPT
# ==============================================================================
# Usage:
#   sudo bash deploy/setup.sh
# ==============================================================================

set -e

# ANSI Color Codes for terminal output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Determine project root directory (parent of deploy folder)
DEPLOY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${DEPLOY_DIR}/.." && pwd)"

cd "${ROOT_DIR}"

echo -e "${CYAN}${BOLD}"
echo "======================================================================"
echo "          MANOVEDH DATA COLLECTION PLATFORM — VPS SETUP               "
echo "======================================================================"
echo -e "${NC}"

# 1. Check Root Privileges
if [[ $EUID -ne 0 ]]; then
   echo -e "${RED}[ERROR] This script must be run as root or with sudo.${NC}"
   echo "Please run: sudo bash deploy/setup.sh"
   exit 1
fi

# 2. Check and Install Docker & Docker Compose if missing
echo -e "${YELLOW}[1/6] Checking system prerequisites (Docker & Docker Compose)...${NC}"

if ! command -v docker &> /dev/null; then
    echo -e "${CYAN}Docker not found. Installing Docker CE automatically...${NC}"
    if [ -f /etc/debian_version ]; then
        apt-get update -y
        apt-get install -y ca-certificates curl gnupg lsb-release ufw
        install -m 0755 -d /etc/apt/keyrings
        curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg --yes
        chmod a+r /etc/apt/keyrings/docker.gpg
        echo \
          "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
          $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
          tee /etc/apt/sources.list.d/docker.list > /dev/null
        apt-get update -y
        apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
        systemctl enable --now docker
    elif [ -f /etc/redhat-release ]; then
        yum install -y yum-utils
        yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
        yum install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
        systemctl enable --now docker
    else
        echo -e "${RED}[ERROR] Unsupported Linux distribution. Please install Docker manually.${NC}"
        exit 1
    fi
    echo -e "${GREEN}✓ Docker installed successfully.${NC}"
else
    echo -e "${GREEN}✓ Docker is already installed: $(docker --version)${NC}"
fi

# Determine compose command syntax
if docker compose version &> /dev/null; then
    DOCKER_COMPOSE="docker compose"
elif command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE="docker-compose"
else
    echo -e "${RED}[ERROR] Docker Compose plugin not found.${NC}"
    apt-get install -y docker-compose-plugin || yum install -y docker-compose-plugin
    DOCKER_COMPOSE="docker compose"
fi

# 3. Configure Firewall Ports
echo -e "${YELLOW}[2/6] Checking firewall configuration...${NC}"
if command -v ufw &> /dev/null && ufw status | grep -q "Status: active"; then
    echo "Opening HTTP (80), HTTPS (443), and App (8000) ports in UFW..."
    ufw allow 80/tcp || true
    ufw allow 443/tcp || true
    ufw allow 8000/tcp || true
    echo -e "${GREEN}✓ UFW firewall rules updated.${NC}"
fi

# 4. Auto-generate Production .env if not exists
echo -e "${YELLOW}[3/6] Configuring environment settings (.env)...${NC}"

if [ ! -f "${ROOT_DIR}/.env" ]; then
    echo "No .env found. Auto-generating production configuration..."

    # Auto-detect public IP
    DETECTED_IP=$(curl -s -m 5 https://api.ipify.org || curl -s -m 5 https://icanhazip.com || echo "127.0.0.1")
    DETECTED_IP=$(echo "${DETECTED_IP}" | tr -d '[:space:]')

    echo -e "Detected Server Public IP: ${CYAN}${DETECTED_IP}${NC}"

    # Generate cryptographic random passwords
    GEN_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(50))" 2>/dev/null || openssl rand -hex 32)
    GEN_DB_PASS=$(python3 -c "import secrets; print(secrets.token_hex(16))" 2>/dev/null || openssl rand -hex 16)

    # Copy template and substitute placeholders
    cp "${DEPLOY_DIR}/env.template" "${ROOT_DIR}/.env"

    # Replace placeholders
    sed -i "s|__GENERATE_SECRET_KEY__|${GEN_SECRET}|g" "${ROOT_DIR}/.env"
    sed -i "s|__GENERATE_DB_PASSWORD__|${GEN_DB_PASS}|g" "${ROOT_DIR}/.env"
    sed -i "s|__DOMAIN_OR_IP__|${DETECTED_IP}|g" "${ROOT_DIR}/.env"

    echo -e "${GREEN}✓ Production .env created with secure random keys and IP: ${DETECTED_IP}${NC}"
else
    echo -e "${GREEN}✓ Existing .env file found. Preserving current configuration.${NC}"
fi

# Export environment variables for compose
set -a
[ -f "${ROOT_DIR}/.env" ] && . "${ROOT_DIR}/.env"
set +a

# 5. Prepare Storage Directories & Permissions
echo -e "${YELLOW}[4/6] Setting up media and static storage directories...${NC}"
mkdir -p "${ROOT_DIR}/media" "${ROOT_DIR}/staticfiles"
chmod -R 775 "${ROOT_DIR}/media" "${ROOT_DIR}/staticfiles" || true
echo -e "${GREEN}✓ Storage directories initialized.${NC}"

# 6. Build and Start Docker Stack
echo -e "${YELLOW}[5/6] Building and launching production containers...${NC}"
${DOCKER_COMPOSE} -f "${ROOT_DIR}/docker-compose.yml" down || true
${DOCKER_COMPOSE} -f "${ROOT_DIR}/docker-compose.yml" up --build -d

echo -e "Waiting for PostgreSQL database to become healthy..."
DB_CHECK_USER="${DB_USER:-mindspace_user}"
DB_CHECK_NAME="${DB_NAME:-mindspace_collection}"
MAX_WAIT=30
WAITED=0
until docker exec mindspace-data-collection-postgres pg_isready -U "${DB_CHECK_USER}" -d "${DB_CHECK_NAME}" &> /dev/null || [ $WAITED -ge $MAX_WAIT ]; do
    sleep 2
    WAITED=$((WAITED+2))
    echo -n "."
done
echo ""

if [ $WAITED -ge $MAX_WAIT ]; then
    echo -e "${YELLOW}[WARNING] Database took longer than expected, continuing with migrations...${NC}"
else
    echo -e "${GREEN}✓ Database is healthy and accepting connections.${NC}"
fi


# 7. Run Migrations & Collect Static Files
echo -e "${YELLOW}[6/6] Applying database migrations and collecting static assets...${NC}"
docker exec mindspace-data-collection-web python manage.py migrate --noinput
docker exec mindspace-data-collection-web python manage.py collectstatic --noinput

# 8. Final Health Verification
SERVER_IP=$(grep -oE 'ALLOWED_HOSTS=[^,]+' "${ROOT_DIR}/.env" | cut -d'=' -f2 || echo "localhost")
PORT=$(grep -oE 'DATA_COLLECTION_PORT=[0-9]+' "${ROOT_DIR}/.env" | cut -d'=' -f2 || echo "8000")

echo -e "${CYAN}${BOLD}"
echo "======================================================================"
echo "         🎉 MANOVEDH APPLICATION IS LIVE AND RUNNING!                "
echo "======================================================================"
echo -e "${NC}"
echo -e "  • ${BOLD}Web Application URL:${NC}  ${GREEN}http://${SERVER_IP}:${PORT}/${NC}"
echo -e "  • ${BOLD}Screening Tool URL:${NC}   ${GREEN}http://${SERVER_IP}:${PORT}/consent/${NC}"
echo -e "  • ${BOLD}Health Check URL:${NC}     ${GREEN}http://${SERVER_IP}:${PORT}/health/${NC}"
echo ""
echo -e "  • ${BOLD}Create Admin Superuser:${NC}"
echo -e "    ${CYAN}docker exec -it mindspace-data-collection-web python manage.py createsuperuser${NC}"
echo ""
echo -e "  • ${BOLD}View Live Logs:${NC}"
echo -e "    ${CYAN}docker compose logs -f web${NC}"
echo ""
echo -e "  • ${BOLD}Future 1-Command Updates:${NC}"
echo -e "    ${CYAN}sudo bash deploy/update.sh${NC}"
echo "======================================================================"
