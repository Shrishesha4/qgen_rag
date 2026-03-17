## 📄 **What [init_data_collection.py](cci:7://file:///Users/niranjankarthick/Dev/qgen_rag/scripts/init_data_collection.py:0:0-0:0) Does**

The [init_data_collection.py](cci:7://file:///Users/niranjankarthick/Dev/qgen_rag/scripts/init_data_collection.py:0:0-0:0) script is the **data collection initialization system** that sets up your SLM/LLM training pipeline. Here's what it does:

### **🎯 Main Purpose**
- **Bootstrap the system** with sample data for training
- **Create the foundation** for continuous learning
- **Establish quality standards** and metrics

### **🔧 Key Functions**

1. **Creates Sample Subjects & Topics**
   - Biology, Computer Science, Physics, Mathematics, Chemistry
   - 5 topics per subject (25 total topics)
   - Provides structure for question generation

2. **Sets Up Vetting Reason Codes**
   - 20+ standardized rejection/approval reasons
   - Categorized by severity (critical, major, minor)
   - Enables consistent feedback collection

3. **Establishes Data Collection Plan**
   - Phase 1: 5000 questions, 2000 approved (2-4 weeks)
   - Phase 2: Model training (1-2 weeks)  
   - Phase 3: Continuous improvement

4. **Defines Training Workflow**
   - Generation → Critique → Vetting → Learning → Improvement
   - Quality gates and thresholds
   - Adaptive learning mechanisms

---

## 🚀 **Step-by-Step Production Setup for vquest.saveetha.com**

### **Phase 1: Server Preparation**

```bash
# 1. Update system and install dependencies
sudo apt update && sudo apt upgrade -y
sudo apt install -y git curl wget nginx certbot python3-certbot-nginx

# 2. Install Docker and NVIDIA Container Toolkit
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# Install NVIDIA Container Toolkit
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list

sudo apt update
sudo apt install -y nvidia-docker2
sudo systemctl restart docker
```

### **Phase 2: Application Deployment**

```bash
# 1. Clone repository
git clone <your-repository-url> /opt/vquest
cd /opt/vquest

# 2. Run DGX setup script
sudo ./scripts/setup_dgx_spark.sh

# 3. Configure production environment
nano /opt/vquest/.env
```

**Critical Environment Variables:**
```bash
# Domain Configuration
DOMAIN=vquest.saveetha.com
SSL_EMAIL=admin@saveetha.com

# Security
SECRET_KEY=$(openssl rand -base64 64)
POSTGRES_PASSWORD=$(openssl rand -base64 32)
REDIS_PASSWORD=$(openssl rand -base64 32)

# External APIs
OPENAI_API_KEY=your_openai_key
DEEPSEEK_API_KEY=your_deepseek_key

# Production Settings
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=INFO
```

### **Phase 3: SSL Certificate Setup**

```bash
# 1. Set up Nginx configuration
sudo nano /etc/nginx/sites-available/vquest
```

**Nginx Config:**
```nginx
server {
    listen 80;
    server_name vquest.saveetha.com;
    
    location / {
        proxy_pass http://localhost:5173;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    location /api {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```bash
# 2. Enable site and get SSL certificate
sudo ln -s /etc/nginx/sites-available/vquest /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx

# 3. Get SSL certificate
sudo certbot --nginx -d vquest.saveetha.com --email admin@saveetha.com --agree-tos --non-interactive
```

### **Phase 4: Production Database Setup**

```bash
# 1. Start services
cd /opt/vquest
docker-compose -f docker-compose.dgx.yml up -d postgres redis

# 2. Initialize database
docker-compose exec backend alembic upgrade head

# 3. Initialize sample data
docker-compose exec backend python scripts/init_data_collection.py
```

### **Phase 5: Application Startup**

```bash
# 1. Start all services
cd /opt/vquest
docker-compose -f docker-compose.dgx.yml up -d

# 2. Verify services
docker-compose ps
curl http://localhost:8000/health
curl http://localhost:5173
```

### **Phase 6: Production Configuration**

```bash
# 1. Create production docker-compose override
nano /opt/vquest/docker-compose.prod.yml
```

**Production Override:**
```yaml
version: '3.8'
services:
  backend:
    environment:
      - ENVIRONMENT=production
      - DEBUG=false
      - LOG_LEVEL=INFO
    restart: always
    deploy:
      replicas: 2
      
  frontend:
    environment:
      - PUBLIC_API_URL=https://vquest.saveetha.com/api
      - PUBLIC_WS_URL=wss://vquest.saveetha.com/ws
    restart: always
    
  nginx:
    image: nginx:alpine
    volumes:
      - ./nginx/prod.conf:/etc/nginx/nginx.conf
      - /etc/letsencrypt:/etc/letsencrypt
    ports:
      - "80:80"
      - "443:443"
    restart: always
```

```bash
# 2. Create production Nginx config
nano /opt/vquest/nginx/prod.conf
```

**Production Nginx Config:**
```nginx
events {
    worker_connections 1024;
}

http {
    upstream backend {
        server backend:8000;
    }
    
    upstream frontend {
        server frontend:5173;
    }
    
    # HTTP to HTTPS redirect
    server {
        listen 80;
        server_name vquest.saveetha.com;
        return 301 https://$server_name$request_uri;
    }
    
    # HTTPS server
    server {
        listen 443 ssl http2;
        server_name vquest.saveetha.com;
        
        ssl_certificate /etc/letsencrypt/live/vquest.saveetha.com/fullchain.pem;
        ssl_certificate_key /etc/letsencrypt/live/vquest.saveetha.com/privkey.pem;
        
        # Security headers
        add_header X-Frame-Options DENY;
        add_header X-Content-Type-Options nosniff;
        add_header X-XSS-Protection "1; mode=block";
        add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
        
        # Frontend
        location / {
            proxy_pass http://frontend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
        
        # Backend API
        location /api {
            proxy_pass http://backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
        
        # WebSocket support
        location /ws {
            proxy_pass http://backend;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
    }
}
```

### **Phase 7: Monitoring & Backup Setup**

```bash
# 1. Set up monitoring
cd /opt/vquest
docker-compose -f docker-compose.dgx.yml up -d prometheus grafana

# 2. Configure backup script
nano /opt/vquest/scripts/backup.sh
```

**Backup Script:**
```bash
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/opt/backups"

# Create backup directory
mkdir -p $BACKUP_DIR

# Database backup
docker-compose exec -T postgres pg_dump -U qgen_user qgen_rag > $BACKUP_DIR/db_$DATE.sql

# Models backup
tar -czf $BACKUP_DIR/models_$DATE.tar.gz /opt/vquest/models/

# Clean old backups (keep 7 days)
find $BACKUP_DIR -name "*.sql" -mtime +7 -delete
find $BACKUP_DIR -name "*.tar.gz" -mtime +7 -delete
```

```bash
# 3. Set up cron job
crontab -e
```

**Cron Jobs:**
```bash
# Backup daily at 2 AM
0 2 * * * /opt/vquest/scripts/backup.sh

# SSL certificate renewal
0 3 * * 1 certbot renew --quiet

# Log rotation
0 4 * * * logrotate /etc/logrotate.d/vquest
```

### **Phase 8: Go Live Checklist**

```bash
# 1. Final verification
curl -I https://vquest.saveetha.com
curl https://vquest.saveetha.com/api/health

# 2. Create admin user
docker-compose exec backend python -c "
from app.core.database import AsyncSessionLocal
from app.models.user import User
from app.services.auth_service import AuthService
import asyncio

async def create_admin():
    async with AsyncSessionLocal() as db:
        service = AuthService(db)
        admin = await service.create_user(
            email='admin@saveetha.com',
            password='your_admin_password',
            full_name='System Administrator',
            role='admin'
        )
        print(f'Admin user created: {admin.id}')

asyncio.run(create_admin())
"

# 3. Initialize data collection
docker-compose exec backend python scripts/init_data_collection.py

# 4. Start full production stack
cd /opt/vquest
docker-compose -f docker-compose.dgx.yml -f docker-compose.prod.yml up -d
```

### **Phase 9: Post-Launch Monitoring**

```bash
# 1. Check service status
docker-compose ps

# 2. Monitor logs
docker-compose logs -f backend
docker-compose logs -f frontend

# 3. Check GPU usage
nvidia-smi

# 4. Access monitoring
# Grafana: https://vquest.saveetha.com:3000
# Prometheus: https://vquest.saveetha.com:9090
```

## 🎯 **Production URLs**

- **Main Application**: https://vquest.saveetha.com
- **Admin Panel**: https://vquest.saveetha.com/admin
- **API Documentation**: https://vquest.saveetha.com/docs
- **Monitoring**: https://vquest.saveetha.com:3000 (Grafana)

## 📊 **Next Steps After Launch**

1. **Create teacher and vetter accounts**
2. **Upload reference documents** for each subject
3. **Start generating questions** (target: 1000+ vetted questions)
4. **Monitor quality metrics** in Grafana
5. **Trigger first training** when you have 1000+ approved questions
6. **Set up automated backups** and monitoring alerts

Your system is now running in production on vquest.saveetha.com with SSL, monitoring, and automatic backups!