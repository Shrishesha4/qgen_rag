#!/bin/bash

# DGX Spark Setup Script for QGen RAG System
# This script sets up the complete environment for training and inference

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
DGX_SETUP_DIR="${DGX_SETUP_DIR:-/opt/qgen}"
MODEL_CACHE_DIR="${MODEL_CACHE_DIR:-$DGX_SETUP_DIR/models}"
LORA_ADAPTERS_DIR="${LORA_ADAPTERS_DIR:-$DGX_SETUP_DIR/lora_adapters}"
TRAINING_DATA_DIR="${TRAINING_DATA_DIR:-$DGX_SETUP_DIR/training_data}"
LOGS_DIR="${LOGS_DIR:-$DGX_SETUP_DIR/logs}"

echo -e "${GREEN}🚀 Setting up QGen RAG on DGX Spark${NC}"

# Check if running on DGX
if [ -f /etc/dgx-release ]; then
    echo -e "${GREEN}✅ Detected DGX environment${NC}"
    DGX_VERSION=$(cat /etc/dgx-release)
    echo -e "${GREEN}   Version: $DGX_VERSION${NC}"
else
    echo -e "${YELLOW}⚠️  Warning: Not running on detected DGX system${NC}"
fi

# Check GPU availability
if command -v nvidia-smi &> /dev/null; then
    echo -e "${GREEN}✅ NVIDIA GPUs detected${NC}"
    nvidia-smi --query-gpu=name,memory.total --format=csv,noheader,nounits | while read line; do
        echo -e "${GREEN}   $line${NC}"
    done
else
    echo -e "${RED}❌ NVIDIA GPUs not detected${NC}"
    exit 1
fi

# Check CUDA
if command -v nvcc &> /dev/null; then
    CUDA_VERSION=$(nvcc --version | grep "release" | awk '{print $6}' | cut -c2-)
    echo -e "${GREEN}✅ CUDA $CUDA_VERSION detected${NC}"
else
    echo -e "${RED}❌ CUDA not found${NC}"
    exit 1
fi

# Create directories
echo -e "${GREEN}📁 Creating directories${NC}"
mkdir -p $DGX_SETUP_DIR
mkdir -p $MODEL_CACHE_DIR
mkdir -p $LORA_ADAPTERS_DIR
mkdir -p $TRAINING_DATA_DIR
mkdir -p $LOGS_DIR

# Set permissions
chmod 755 $DGX_SETUP_DIR
chmod 755 $MODEL_CACHE_DIR
chmod 755 $LORA_ADAPTERS_DIR
chmod 755 $TRAINING_DATA_DIR
chmod 755 $LOGS_DIR

# Install Docker if not present
if ! command -v docker &> /dev/null; then
    echo -e "${GREEN}🐳 Installing Docker${NC}"
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
    systemctl start docker
    systemctl enable docker
    usermod -aG docker $USER
else
    echo -e "${GREEN}✅ Docker already installed${NC}"
fi

# Install Docker Compose if not present
if ! command -v docker-compose &> /dev/null; then
    echo -e "${GREEN}🐳 Installing Docker Compose${NC}"
    curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
else
    echo -e "${GREEN}✅ Docker Compose already installed${NC}"
fi

# Install NVIDIA Container Toolkit
echo -e "${GREEN}🔧 Installing NVIDIA Container Toolkit${NC}"
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list

apt-get update && apt-get install -y nvidia-docker2
systemctl restart docker

# Configure Docker for NVIDIA runtime
echo -e "${GREEN}⚙️  Configuring Docker for NVIDIA${NC}"
cat > /etc/docker/daemon.json <<EOF
{
    "default-runtime": "nvidia",
    "runtimes": {
        "nvidia": {
            "path": "nvidia-container-runtime",
            "runtimeArgs": []
        }
    }
}
EOF

systemctl restart docker

# Create environment file
echo -e "${GREEN}📝 Creating environment file${NC}"
cat > $DGX_SETUP_DIR/.env <<EOF
# Database Configuration
POSTGRES_PASSWORD=$(openssl rand -base64 32)
REDIS_PASSWORD=$(openssl rand -base64 32)

# Model Configuration
LOCAL_MODEL_PATH=deepseek-ai/DeepSeek-R1-Distill-Llama-8B
MODEL_CACHE_DIR=$MODEL_CACHE_DIR
LORA_ADAPTERS_DIR=$LORA_ADAPTERS_DIR
TRAINING_DATA_DIR=$TRAINING_DATA_DIR

# GPU Optimization
CUDA_VISIBLE_DEVICES=0,1,2,3
USE_FLASH_ATTN=true
USE_4BIT=true
MAX_NEW_TOKENS=2048
BATCH_SIZE=4
MAX_BATCH_SIZE=8

# Security
SECRET_KEY=$(openssl rand -base64 32)

# Training Configuration
TRAINING_BASE_MODEL=deepseek-ai/DeepSeek-R1-Distill-Llama-8B
LEARNING_RATE=2e-4
BATCH_SIZE=2
GRADIENT_ACCUMULATION_STEPS=8
LORA_R=16
LORA_ALPHA=32
NUM_EPOCHS=3

# Monitoring
GRAFANA_PASSWORD=admin

# External APIs (set these as needed)
# OPENAI_API_KEY=your_openai_key
# DEEPSEEK_API_KEY=your_deepseek_key
EOF

echo -e "${GREEN}✅ Environment file created at $DGX_SETUP_DIR/.env${NC}"

# Download base model
echo -e "${GREEN}📥 Downloading base model (this may take a while)...${NC}"
cd $DGX_SETUP_DIR

# Create a simple download script
cat > download_model.py <<'EOF'
#!/usr/bin/env python
import os
from transformers import AutoTokenizer, AutoModelForCausalLM
import torch

model_name = os.environ.get("LOCAL_MODEL_PATH", "deepseek-ai/DeepSeek-R1-Distill-Llama-8B")
cache_dir = os.environ.get("MODEL_CACHE_DIR", "./models")

print(f"Downloading model: {model_name}")
print(f"Cache directory: {cache_dir}")

try:
    # Download tokenizer
    print("Downloading tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(model_name, cache_dir=cache_dir)
    
    # Download model (without loading to save memory)
    print("Downloading model weights...")
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        cache_dir=cache_dir,
        torch_dtype=torch.float16,
        device_map="cpu"  # Don't load to GPU yet
    )
    
    print("✅ Model download completed successfully")
    
except Exception as e:
    print(f"❌ Model download failed: {e}")
    exit(1)
EOF

python3 download_model.py

# Setup systemd service for auto-start
echo -e "${GREEN}🔧 Setting up systemd service${NC}"
cat > /etc/systemd/system/qgen-rag.service <<EOF
[Unit]
Description=QGen RAG System
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=$DGX_SETUP_DIR
ExecStart=/usr/local/bin/docker-compose -f docker-compose.dgx.yml up -d
ExecStop=/usr/local/bin/docker-compose -f docker-compose.dgx.yml down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable qgen-rag.service

# Create monitoring setup
echo -e "${GREEN}📊 Setting up monitoring${NC}"
mkdir -p $DGX_SETUP_DIR/monitoring

cat > $DGX_SETUP_DIR/monitoring/prometheus.yml <<EOF
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'qgen-backend'
    static_configs:
      - targets: ['backend:8000']
    metrics_path: '/metrics'
    scrape_interval: 30s

  - job_name: 'qgen-training'
    static_configs:
      - targets: ['training_worker:8001']
    metrics_path: '/metrics'
    scrape_interval: 60s

  - job_name: 'node-exporter'
    static_configs:
      - targets: ['node-exporter:9100']
EOF

# Setup log rotation
echo -e "${GREEN}📋 Setting up log rotation${NC}"
cat > /etc/logrotate.d/qgen-rag <<EOF
$LOGS_DIR/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 root root
    postrotate
        docker-compose -f $DGX_SETUP_DIR/docker-compose.dgx.yml restart backend
    endscript
}
EOF

# Print setup summary
echo -e "${GREEN}🎉 DGX Spark setup completed!${NC}"
echo ""
echo -e "${GREEN}📍 Directories:${NC}"
echo -e "   Setup: $DGX_SETUP_DIR"
echo -e "   Models: $MODEL_CACHE_DIR"
echo -e "   Adapters: $LORA_ADAPTERS_DIR"
echo -e "   Training Data: $TRAINING_DATA_DIR"
echo -e "   Logs: $LOGS_DIR"
echo ""
echo -e "${GREEN}🚀 To start the system:${NC}"
echo -e "   cd $DGX_SETUP_DIR"
echo -e "   docker-compose -f docker-compose.dgx.yml up -d"
echo ""
echo -e "${GREEN}🔍 To check status:${NC}"
echo -e "   docker-compose -f docker-compose.dgx.yml ps"
echo ""
echo -e "${GREEN}📊 Monitoring:${NC}"
echo -e "   Grafana: http://localhost:3000 (admin/admin)"
echo -e "   Prometheus: http://localhost:9090"
echo ""
echo -e "${GREEN}📚 Next steps:${NC}"
echo -e "   1. Set your API keys in $DGX_SETUP_DIR/.env"
echo -e "   2. Start the system with the command above"
echo -e "   3. Navigate to http://localhost:5173 to begin"
echo -e "   4. Check the deployment guide for data collection instructions"

echo -e "${GREEN}✅ Setup complete!${NC}"
