#!/bin/bash
# QGen RAG Setup Launcher for macOS/Linux
# This script launches the cross-platform setup system

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 QGen RAG Interactive Setup Launcher${NC}"
echo -e "${BLUE}====================================${NC}"
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    if ! command -v python &> /dev/null; then
        echo -e "${RED}❌ Python is not installed${NC}"
        echo "Please install Python 3.9 or higher"
        exit 1
    else
        PYTHON_CMD="python"
    fi
else
    PYTHON_CMD="python3"
fi

# Check Python version
PYTHON_VERSION=$($PYTHON_CMD -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
echo -e "${GREEN}✅ Python $PYTHON_VERSION detected${NC}"

# Check if we're in the right directory
if [ ! -f "scripts/interactive_setup.py" ]; then
    echo -e "${RED}❌ interactive_setup.py not found in scripts directory${NC}"
    echo "Please run this script from the project root directory"
    exit 1
fi

# Check system requirements
echo -e "${BLUE}🔍 Checking system requirements...${NC}"

# Check for Docker
if command -v docker &> /dev/null; then
    echo -e "${GREEN}✅ Docker is installed${NC}"
    if docker info &> /dev/null; then
        echo -e "${GREEN}✅ Docker is running${NC}"
    else
        echo -e "${YELLOW}⚠️  Docker is installed but not running${NC}"
        echo "Please start Docker before proceeding"
    fi
else
    echo -e "${YELLOW}⚠️  Docker is not installed${NC}"
    echo "The setup script can install Docker for you"
fi

# Check for Git
if command -v git &> /dev/null; then
    echo -e "${GREEN}✅ Git is installed${NC}"
else
    echo -e "${YELLOW}⚠️  Git is not installed${NC}"
    echo "The setup script can install Git for you"
fi

# Detect platform
PLATFORM=$(uname -s)
echo -e "${BLUE}🖥️  Platform: $PLATFORM${NC}"

if [ "$PLATFORM" = "Darwin" ]; then
    # macOS specific checks
    if [ "$(uname -m)" = "arm64" ]; then
        echo -e "${GREEN}🚀 Apple Silicon Mac detected${NC}"
    else
        echo -e "${GREEN}🖥️  Intel Mac detected${NC}"
    fi
    
    # Check for Homebrew
    if command -v brew &> /dev/null; then
        echo -e "${GREEN}✅ Homebrew is available${NC}"
    else
        echo -e "${YELLOW}⚠️  Homebrew not found - will be installed${NC}"
    fi
elif [ "$PLATFORM" = "Linux" ]; then
    # Linux specific checks
    echo -e "${GREEN}🐧 Linux detected${NC}"
    
    # Check package manager
    if command -v apt-get &> /dev/null; then
        echo -e "${GREEN}📦 APT package manager detected${NC}"
    elif command -v yum &> /dev/null; then
        echo -e "${GREEN}📦 YUM package manager detected${NC}"
    elif command -v pacman &> /dev/null; then
        echo -e "${GREEN}📦 Pacman package manager detected${NC}"
    else
        echo -e "${YELLOW}⚠️  Unknown package manager${NC}"
    fi
fi

echo ""
echo -e "${BLUE}🌐 Starting cross-platform setup launcher...${NC}"

# Run the cross-platform launcher
python launch_setup.py

echo ""
echo -e "${GREEN}✅ Setup completed successfully!${NC}"
