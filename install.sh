#!/bin/bash

# 检查是否为 root 用户
if [ $(id -u) -ne 0 ]; then
    echo "This script must be run as root" 1>&2
    exit 1
fi

echo "Starting PPress installation..."

# 检查 Python 版本
echo "Checking Python version..."
if command -v python3 >/dev/null 2>&1; then
    PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
    if [ "$(echo "$PYTHON_VERSION >= 3.8" | bc)" -eq 1 ]; then
        echo "Python $PYTHON_VERSION is already installed and meets requirements."
        INSTALL_PYTHON=0
    else
        echo "Python $PYTHON_VERSION is too old, need >= 3.8"
        INSTALL_PYTHON=1
    fi
else
    echo "Python 3 not found"
    INSTALL_PYTHON=1
fi

echo "Checking your location..."

# 通过访问谷歌来判断是否在中国
if curl -s --connect-timeout 3 --max-time 5 www.google.com &>/dev/null; then
    echo "Detected international network..."
    is_china_ip=0
else
    echo "Detected China network..."
    is_china_ip=1
fi

# 设置仓库地址
if [ "$is_china_ip" -eq 1 ]; then
    echo "Using Gitee repository..."
    export REPOSITORY_URL='https://gitee.com/fojie/PPress.git'
else
    echo "Using GitHub repository..."
    export REPOSITORY_URL='https://github.com/yandaozi/PPress.git'
fi

# 如果需要安装 Python
if [ "$INSTALL_PYTHON" -eq 1 ]; then
    # 设置 Python 源
    if [ "$is_china_ip" -eq 1 ]; then
        echo "Using China mirrors..."
        export PYTHON_SOURCE='https://mirrors.huaweicloud.com/python/3.12.3/Python-3.12.3.tgz'
        export PIP_SOURCE='https://pypi.tuna.tsinghua.edu.cn/simple/'
    else
        echo "Using international mirrors..."
        export PYTHON_SOURCE='https://www.python.org/ftp/python/3.12.3/Python-3.12.3.tgz'
        export PIP_SOURCE='https://pypi.org/simple/'
    fi

    # 安装必要的工具和依赖
    echo "Installing required packages..."
    yum groupinstall -y "Development Tools"
    yum install -y gcc gcc-c++ make \
        openssl-devel bzip2-devel libffi-devel \
        zlib-devel xz-devel sqlite-devel \
        readline-devel tk-devel ncurses-devel \
        gdbm-devel db4-devel expat-devel \
        curl git wget

    # 安装 Python 3.12
    echo "Installing Python 3.12..."
    cd /opt
    echo "Downloading Python source code..."
    wget $PYTHON_SOURCE 2>&1 | \
        while read line; do
            echo -ne "\rDownloading... $line"
        done
    echo -e "\nDownload completed."

    echo "Extracting Python source code..."
    if [ -f "$(basename $PYTHON_SOURCE)" ]; then
        tar -zxf $(basename $PYTHON_SOURCE)
    else
        echo "Error: Python source file not found"
        exit 1
    fi

    if [ ! -d "Python-3.12.3" ]; then
        echo "Error: Python source directory not found"
        exit 1
    fi

    cd $(basename $PYTHON_SOURCE | sed 's/.tgz//')
    echo "Configuring Python build..."
    # 清理之前的构建
    make clean || true

    # 配置 Python 构建
    ./configure \
        --prefix=/usr/local \
        --enable-shared \
        --with-system-expat \
        --with-system-ffi \
        --enable-loadable-sqlite-extensions \
        --with-ensurepip=yes \
        LDFLAGS="-Wl,-rpath /usr/local/lib"

    echo "Building Python (this may take a while)..."
    # 编译和安装
    CPU_CORES=$(nproc)
    echo "Using $CPU_CORES CPU cores for compilation..."
    make -j$CPU_CORES
    make install

    # 创建软链接
    ln -sf /usr/local/bin/python3.12 /usr/local/bin/python3
    ln -sf /usr/local/bin/pip3.12 /usr/local/bin/pip3
fi

# 配置pip默认源
mkdir -p ~/.pip
if [ "$is_china_ip" -eq 1 ]; then
    echo "[global]
    index-url = https://pypi.tuna.tsinghua.edu.cn/simple/
    trusted-host = pypi.tuna.tsinghua.edu.cn" > ~/.pip/pip.conf
fi

# 克隆 PPress 代码
echo "Cloning PPress repository..."
cd /opt
git clone --depth=1 $REPOSITORY_URL
cd PPress

# 安装 PPress 依赖
echo "Installing PPress dependencies..."
pip3.12 install -r requirements.txt -i $PIP_SOURCE --no-cache-dir -U

# 询问用户想要运行的端口
echo
echo "Installation completed!"
read -p "Please enter the port on which you want to run PPress (default: 5000): " PORT
PORT=${PORT:-5000}

# 配置防火墙
echo "Configuring firewall..."
if command -v firewall-cmd >/dev/null 2>&1; then
    # 如果是 firewalld
    firewall-cmd --permanent --add-port=${PORT}/tcp
    firewall-cmd --reload
    echo "Firewall port ${PORT} opened (firewalld)"
elif command -v iptables >/dev/null 2>&1; then
    # 如果是 iptables
    iptables -I INPUT -p tcp --dport ${PORT} -j ACCEPT
    service iptables save
    echo "Firewall port ${PORT} opened (iptables)"
else
    echo "Warning: No firewall management tool found"
fi

echo "Starting PPress on port $PORT..."
# 运行 PPress
export FLASK_APP=run.py
flask run --host=0.0.0.0 --port=$PORT

# 创建 ppress 命令
echo "Creating ppress command..."
cat > /usr/local/bin/ppress << 'EOF'
#!/bin/bash

# PPress 配置文件
CONFIG_FILE="/etc/ppress.conf"
PID_FILE="/var/run/ppress.pid"
LOG_FILE="/var/log/ppress.log"

# 如果配置文件不存在则创建
if [ ! -f "$CONFIG_FILE" ]; then
    echo "PORT=5000" > "$CONFIG_FILE"
fi

# 加载配置
source "$CONFIG_FILE"

# 获取运行状态
get_status() {
    if [ -f "$PID_FILE" ] && kill -0 $(cat "$PID_FILE") 2>/dev/null; then
        local pid=$(cat "$PID_FILE")
        local port=$(grep "PORT=" "$CONFIG_FILE" | cut -d= -f2)
        echo "Status: Running"
        echo "PID: $pid"
        echo "Port: $port"
        echo "URL: http://$(hostname -I | awk '{print $1}'):$port"
    else
        echo "Status: Stopped"
    fi
}

# 启动服务
start() {
    if [ -f "$PID_FILE" ] && kill -0 $(cat "$PID_FILE") 2>/dev/null; then
        echo "PPress is already running."
        get_status
        return
    fi
    
    cd /opt/PPress
    export FLASK_APP=run.py
    nohup flask run --host=0.0.0.0 --port=$PORT > "$LOG_FILE" 2>&1 & echo $! > "$PID_FILE"
    echo "PPress started."
    get_status
}

# 停止服务
stop() {
    if [ -f "$PID_FILE" ]; then
        kill $(cat "$PID_FILE")
        rm "$PID_FILE"
        echo "PPress stopped."
    else
        echo "PPress is not running."
    fi
}

# 重启服务
restart() {
    stop
    sleep 2
    start
}

# 修改端口
change_port() {
    read -p "Enter new port number: " new_port
    if [[ "$new_port" =~ ^[0-9]+$ ]]; then
        # 保存旧端口号
        old_port=$PORT
        
        # 配置防火墙
        if command -v firewall-cmd >/dev/null 2>&1; then
            firewall-cmd --permanent --remove-port=$old_port/tcp
            firewall-cmd --permanent --add-port=$new_port/tcp
            firewall-cmd --reload
        elif command -v iptables >/dev/null 2>&1; then
            iptables -D INPUT -p tcp --dport $old_port -j ACCEPT
            iptables -I INPUT -p tcp --dport $new_port -j ACCEPT
            service iptables save
        fi
        
        # 更新配置文件
        sed -i "s/PORT=.*/PORT=$new_port/" "$CONFIG_FILE"
        # 重新加载配置
        source "$CONFIG_FILE"
        echo "Port changed to $new_port"
        
        # 如果服务正在运行，则重启
        if [ -f "$PID_FILE" ] && kill -0 $(cat "$PID_FILE") 2>/dev/null; then
            echo "Restarting PPress with new port..."
            stop
            sleep 2
            start
        else
            echo "PPress is not running. Start it with 'ppress start' to use the new port."
        fi
    else
        echo "Invalid port number"
    fi
}

# 显示帮助信息
show_help() {
    echo "Usage: ppress <command>"
    echo "Commands:"
    echo "  status    - Show current status"
    echo "  start     - Start PPress"
    echo "  stop      - Stop PPress"
    echo "  restart   - Restart PPress"
    echo "  port      - Change port"
    echo "  help      - Show this help"
}

# 主命令处理
case "$1" in
    status)
        get_status
        ;;
    start)
        start
        ;;
    stop)
        stop
        ;;
    restart)
        restart
        ;;
    port)
        change_port
        ;;
    help|"")
        show_help
        ;;
    *)
        echo "Unknown command: $1"
        show_help
        exit 1
        ;;
esac
EOF

# 设置执行权限
chmod +x /usr/local/bin/ppress

# 创建初始配置文件
echo "PORT=$PORT" > /etc/ppress.conf

echo "PPress command installed. Type 'ppress help' for usage."

# 启动服务
ppress start