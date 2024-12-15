#!/bin/bash

# 检查是否为 root 用户
if [ $(id -u) -ne 0 ]; then
    echo "This script must be run as root" 1>&2
    exit 1
fi

echo "Starting PPress installation..."
echo "Checking your location..."

# 通过访问谷歌来判断是否在中国
if curl -s --connect-timeout 3 --max-time 5 www.google.com &>/dev/null; then
    echo "Detected international network..."
    is_china_ip=0
else
    echo "Detected China network..."
    is_china_ip=1
fi

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

# 设置仓库地址
if [ "$is_china_ip" -eq 1 ]; then
    echo "Using Gitee repository..."
    export REPOSITORY_URL='https://gitee.com/fojie/PPress.git'
else
    echo "Using GitHub repository..."
    export REPOSITORY_URL='https://github.com/yandaozi/PPress.git'
fi

# 安装必要的工具和依赖
echo "Installing required packages..."
yum install -y gcc openssl-devel bzip2-devel libffi-devel zlib-devel curl git

# 安装 Python 3.12
echo "Installing Python 3.12..."
cd /opt
echo "Downloading Python source code..."
wget -q --show-progress $PYTHON_SOURCE
echo "Extracting Python source code..."
tar -zxf $(basename $PYTHON_SOURCE)
cd $(basename $PYTHON_SOURCE | sed 's/.tgz//')
echo "Configuring Python build..."
./configure --prefix=/usr/local/python3.12 --enable-shared LDFLAGS="-Wl,-rpath /usr/local/python3.12/lib"
echo "Building Python (this may take a while)..."
make -j$(nproc) altinstall

# 安装 pip
echo "Installing pip..."
curl -s https://bootstrap.pypa.io/get-pip.py | python3.12

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
        # 配置防火墙
        if command -v firewall-cmd >/dev/null 2>&1; then
            firewall-cmd --permanent --remove-port=$PORT/tcp
            firewall-cmd --permanent --add-port=$new_port/tcp
            firewall-cmd --reload
        elif command -v iptables >/dev/null 2>&1; then
            iptables -D INPUT -p tcp --dport $PORT -j ACCEPT
            iptables -I INPUT -p tcp --dport $new_port -j ACCEPT
            service iptables save
        fi
        
        # 更新配置文件
        sed -i "s/PORT=.*/PORT=$new_port/" "$CONFIG_FILE"
        echo "Port changed to $new_port"
        
        # 如果服务正在运行，则重启
        if [ -f "$PID_FILE" ] && kill -0 $(cat "$PID_FILE") 2>/dev/null; then
            restart
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