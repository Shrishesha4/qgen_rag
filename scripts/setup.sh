#!/bin/bash

# QGen RAG Interactive Setup Launcher
# This script launches the interactive web-based setup system

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo -e "${BLUE}🚀 QGen RAG Interactive Setup${NC}"
echo -e "${BLUE}================================${NC}"
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 is required but not installed${NC}"
    echo "Please install Python 3.9 or higher"
    exit 1
fi

# Check Python version
PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
REQUIRED_VERSION="3.9"

if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
    echo -e "${RED}❌ Python $REQUIRED_VERSION or higher is required (found $PYTHON_VERSION)${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Python $PYTHON_VERSION detected${NC}"

# Check if we're in the right directory
if [ ! -f "$PROJECT_ROOT/docker-compose.dgx.yml" ]; then
    echo -e "${YELLOW}⚠️  Warning: docker-compose.dgx.yml not found in project root${NC}"
    echo "Make sure you're running this from the correct project directory"
fi

# Install requirements
echo -e "${BLUE}📦 Installing setup requirements...${NC}"
cd "$SCRIPT_DIR"

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo -e "${BLUE}🔧 Creating virtual environment...${NC}"
    python3 -m venv venv
fi

# Activate virtual environment
echo -e "${BLUE}🔧 Activating virtual environment...${NC}"
source venv/bin/activate

# Install requirements
echo -e "${BLUE}📦 Installing Python packages...${NC}"
pip install -r setup_requirements.txt

# Check for system requirements
echo -e "${BLUE}🔍 Checking system requirements...${NC}"

# Check Docker
if command -v docker &> /dev/null; then
    echo -e "${GREEN}✅ Docker is installed${NC}"
    if docker info &> /dev/null; then
        echo -e "${GREEN}✅ Docker is running${NC}"
    else
        echo -e "${YELLOW}⚠️  Docker is installed but not running${NC}"
        echo "Please start Docker before proceeding with setup"
    fi
else
    echo -e "${YELLOW}⚠️  Docker is not installed${NC}"
    echo "The setup script can install Docker for you"
fi

# Check Docker Compose
if command -v docker-compose &> /dev/null; then
    echo -e "${GREEN}✅ Docker Compose is installed${NC}"
else
    echo -e "${YELLOW}⚠️  Docker Compose is not installed${NC}"
    echo "The setup script can install Docker Compose for you"
fi

# Check Git
if command -v git &> /dev/null; then
    echo -e "${GREEN}✅ Git is installed${NC}"
else
    echo -e "${YELLOW}⚠️  Git is not installed${NC}"
    echo "The setup script can install Git for you"
fi

# Check for NVIDIA GPU (optional)
if command -v nvidia-smi &> /dev/null; then
    GPU_COUNT=$(nvidia-smi --list-gpus | wc -l)
    echo -e "${GREEN}✅ NVIDIA GPU detected ($GPU_COUNT GPUs)${NC}"
    echo "GPU acceleration will be available"
else
    echo -e "${YELLOW}⚠️  No NVIDIA GPU detected${NC}"
    echo "The system will run in CPU-only mode"
fi

# Check available ports
echo -e "${BLUE}🔍 Checking available ports...${NC}"

if lsof -i :8080 &> /dev/null; then
    echo -e "${YELLOW}⚠️  Port 8080 is already in use${NC}"
    echo "The setup will use a different port"
    SETUP_PORT=8081
else
    SETUP_PORT=8080
fi

echo -e "${GREEN}✅ Port $SETUP_PORT is available${NC}"

# Start the interactive setup
echo ""
echo -e "${BLUE}🌐 Starting interactive web setup...${NC}"
echo -e "${BLUE}📋 Open your browser and go to:${NC}"
echo -e "${GREEN}   http://localhost:$SETUP_PORT${NC}"
echo ""
echo -e "${BLUE}The setup will:${NC}"
echo -e "   • Detect your system configuration"
echo -e "   • Guide you through configuration"
echo -e "   • Install dependencies automatically"
echo -e "   • Set up the complete system"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop the setup server${NC}"
echo ""

# Change to project directory
cd "$PROJECT_ROOT"

# Start the setup server
export SETUP_PORT=$SETUP_PORT
python3 "$SCRIPT_DIR/interactive_setup.py"
