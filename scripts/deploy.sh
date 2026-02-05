#!/bin/bash
# Qwen Social Agent Pro - 一键部署脚本
# 适用于 Ubuntu 22.04 (Vultr/AWS/GCP)

set -e

# ==================== 配置变量 ====================
PROJECT_NAME="qwen-social-agent-pro"
PROJECT_DIR="/opt/$PROJECT_NAME"
DOCKER_COMPOSE_VERSION="2.23.0"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# ==================== 系统检查 ====================
check_system() {
    log_info "检查系统环境..."
    
    # 检查是否为 root
    if [ "$EUID" -ne 0 ]; then
        log_error "请使用 root 权限运行此脚本"
        exit 1
    fi
    
    # 检查系统版本
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        if [ "$ID" != "ubuntu" ]; then
            log_warn "此脚本针对 Ubuntu 优化，其他系统可能需要调整"
        fi
    fi
    
    # 检查内存
    TOTAL_MEM=$(free -g | awk '/^Mem:/{print $2}')
    if [ "$TOTAL_MEM" -lt 4 ]; then
        log_warn "建议至少 4GB 内存，当前: ${TOTAL_MEM}GB"
    fi
    
    log_info "系统检查完成"
}

# ==================== 安装依赖 ====================
install_dependencies() {
    log_info "安装系统依赖..."
    
    apt-get update
    apt-get install -y \
        apt-transport-https \
        ca-certificates \
        curl \
        gnupg \
        lsb-release \
        git \
        jq
    
    log_info "系统依赖安装完成"
}

# ==================== 安装 Docker ====================
install_docker() {
    if command -v docker &> /dev/null; then
        log_info "Docker 已安装，跳过..."
        return
    fi
    
    log_info "安装 Docker..."
    
    # 添加 Docker 官方 GPG 密钥
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
    
    # 添加 Docker 仓库
    echo \
        "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu \
        $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
    
    # 安装 Docker
    apt-get update
    apt-get install -y docker-ce docker-ce-cli containerd.io
    
    # 启动 Docker
    systemctl start docker
    systemctl enable docker
    
    log_info "Docker 安装完成"
}

# ==================== 安装 Docker Compose ====================
install_docker_compose() {
    if command -v docker-compose &> /dev/null || docker compose version &> /dev/null; then
        log_info "Docker Compose 已安装，跳过..."
        return
    fi
    
    log_info "安装 Docker Compose..."
    
    curl -SL "https://github.com/docker/compose/releases/download/v${DOCKER_COMPOSE_VERSION}/docker-compose-linux-$(uname -m)" \
        -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
    
    log_info "Docker Compose 安装完成"
}

# ==================== 安装 NVIDIA Docker（可选） ====================
install_nvidia_docker() {
    if ! command -v nvidia-smi &> /dev/null; then
        log_warn "未检测到 NVIDIA GPU，跳过 NVIDIA Docker 安装"
        return
    fi
    
    log_info "安装 NVIDIA Docker..."
    
    distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
    curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | apt-key add -
    curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | \
        tee /etc/apt/sources.list.d/nvidia-docker.list
    
    apt-get update
    apt-get install -y nvidia-docker2
    
    systemctl restart docker
    
    log_info "NVIDIA Docker 安装完成"
}

# ==================== 部署应用 ====================
deploy_application() {
    log_info "部署应用..."
    
    # 创建项目目录
    mkdir -p $PROJECT_DIR
    cd $PROJECT_DIR
    
    # 如果是 Git 仓库，拉取代码
    if [ -d ".git" ]; then
        git pull
    else
        # 复制当前目录的文件
        cp -r /home/ubuntu/$PROJECT_NAME/* $PROJECT_DIR/ 2>/dev/null || true
    fi
    
    # 创建环境变量文件
    if [ ! -f ".env" ]; then
        log_info "创建环境变量文件..."
        cat > .env << EOF
# Environment
ENVIRONMENT=production
DEBUG=false

# Server
HOST=0.0.0.0
PORT=8000

# LLM
LLM_MODEL=qwen:1.8b
OLLAMA_BASE_URL=http://ollama:11434

# Redis
REDIS_URL=redis://redis:6379/0

# ChromaDB
CHROMA_HOST=chromadb
CHROMA_PORT=8001

# API Keys (请填写)
# OPENAI_API_KEY=
# SERPER_API_KEY=
# TAVILY_API_KEY=
EOF
    fi
    
    # 启动服务
    log_info "启动 Docker 服务..."
    docker compose up -d
    
    # 等待服务启动
    log_info "等待服务启动..."
    sleep 10
    
    # 下载 Qwen 模型
    log_info "下载 Qwen 模型（这可能需要几分钟）..."
    docker exec qwen-ollama ollama pull qwen:1.8b || true
    
    log_info "应用部署完成"
}

# ==================== 配置防火墙 ====================
configure_firewall() {
    log_info "配置防火墙..."
    
    if command -v ufw &> /dev/null; then
        ufw allow 22/tcp
        ufw allow 80/tcp
        ufw allow 443/tcp
        ufw allow 8000/tcp
        ufw --force enable
    fi
    
    log_info "防火墙配置完成"
}

# ==================== 显示状态 ====================
show_status() {
    log_info "==================== 部署完成 ===================="
    echo ""
    echo "服务状态:"
    docker compose ps
    echo ""
    echo "访问地址:"
    echo "  - API: http://$(curl -s ifconfig.me):8000"
    echo "  - 文档: http://$(curl -s ifconfig.me):8000/docs"
    echo ""
    echo "常用命令:"
    echo "  - 查看日志: docker compose logs -f"
    echo "  - 重启服务: docker compose restart"
    echo "  - 停止服务: docker compose down"
    echo ""
    log_info "=================================================="
}

# ==================== 主函数 ====================
main() {
    log_info "开始部署 $PROJECT_NAME"
    
    check_system
    install_dependencies
    install_docker
    install_docker_compose
    install_nvidia_docker
    deploy_application
    configure_firewall
    show_status
    
    log_info "部署完成！"
}

# 运行主函数
main "$@"
