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
yum update -y
yum install -y gcc openssl-devel bzip2-devel libffi-devel zlib-devel curl git

# 安装 Python 3.12
echo "Installing Python 3.12..."
cd /opt
echo "Downloading Python source code..."
wget $PYTHON_SOURCE
echo "Extracting Python source code..."
tar -zxvf $(basename $PYTHON_SOURCE)
cd $(basename $PYTHON_SOURCE | sed 's/.tgz//')
echo "Configuring Python build..."
./configure --enable-optimizations
echo "Building Python (this may take a while)..."
make altinstall

# 安装 pip
echo "Installing pip..."
python3.12 get-pip.py

# 克隆 PPress 代码
echo "Cloning PPress repository..."
cd /opt
git clone $REPOSITORY_URL
cd PPress

# 安装 PPress 依赖
echo "Installing PPress dependencies..."
pip3.12 install -r requirements.txt -i $PIP_SOURCE

# 询问用户想要运行的端口
echo
echo "Installation completed!"
read -p "Please enter the port on which you want to run PPress (default: 5000): " PORT
PORT=${PORT:-5000}

echo "Starting PPress on port $PORT..."
# 运行 PPress
export FLASK_APP=run.py
flask run --host=0.0.0.0 --port=$PORT