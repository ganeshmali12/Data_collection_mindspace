# 🚀 Manovedh VPS Deployment Guide

Deploy the Manovedh Multimodal Mental Health Data Collection platform to any Linux VPS (Ubuntu, Debian, CentOS, AlmaLinux) in a **single command**.

---

## ⚡ Quick Start (1-Command Setup)

### 1. Connect to your VPS via SSH
```bash
ssh root@your-vps-ip
```

### 2. Clone the Repository
```bash
git clone <YOUR_GIT_REPOSITORY_URL>
cd Data_collection_mindspace
```

### 3. Run the Setup Script
```bash
sudo bash deploy/setup.sh
```

**That's it!** The setup script will automatically:
1. Detect and install **Docker** & **Docker Compose** if missing.
2. Auto-generate a secure `.env` file with random secret keys and your server's public IP.
3. Configure storage and permissions for media recordings.
4. Build and start the PostgreSQL and Django ASGI containers.
5. Run all database migrations and collect static files.
6. Verify service health and output your live application URL.

---

## 🔄 Updating the Application (1-Command Update)

Whenever you push new code to your Git repository, run this command on your VPS to update without downtime:

```bash
sudo bash deploy/update.sh
```

---

## 🌐 Custom Domain & SSL (Optional)

If you have a domain pointing to your VPS (e.g. `screening.yourdomain.com`):

1. Edit your `.env` file:
   ```bash
   nano .env
   ```
2. Update `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS`:
   ```ini
   ALLOWED_HOSTS=screening.yourdomain.com,127.0.0.1,localhost
   CSRF_TRUSTED_ORIGINS=https://screening.yourdomain.com,http://screening.yourdomain.com
   ```
3. Restart containers:
   ```bash
   docker compose up -d
   ```

### Enabling Let's Encrypt Free SSL via Nginx (Optional)
If you want to use the included Nginx reverse proxy with automated SSL:
```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d screening.yourdomain.com
```

---

## 🛠️ Useful Management Commands

| Task | Command |
|---|---|
| **View Live Logs** | `docker compose logs -f web` |
| **Create Admin User** | `docker exec -it mindspace-data-collection-web python manage.py createsuperuser` |
| **Restart Services** | `docker compose restart` |
| **Stop Application** | `docker compose down` |
| **Check Container Health** | `docker compose ps` |
| **Database Backup** | `docker exec mindspace-data-collection-postgres pg_dump -U mindspace_user mindspace_collection > backup.sql` |
| **Database Restore** | `cat backup.sql \| docker exec -i mindspace-data-collection-postgres psql -U mindspace_user mindspace_collection` |

---

## 📁 File Structure in `deploy/`

```
deploy/
├── setup.sh                 # Master 1-command deployment script
├── update.sh                # 1-command git pull & rebuild script
├── env.template             # Production environment template
├── docker-compose.prod.yml  # Production Docker Compose specification with Nginx
├── nginx/
│   └── default.conf         # Nginx reverse-proxy configuration (250MB uploads, Gzip)
└── README.md                # This guide
```
