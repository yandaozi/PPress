#!/bin/bash

# 检查是否为 root 用户
if [ "$(id -u)"!= "0" ]; then
    echo "This script must be run as root" 1>&2
    exit 1
fi

# 获取 IP 地址信息
ip_info=$(curl -s 'https://ipapi.co/json/')

# 判断是否是中国 IP
is_china_ip=$(echo "$ip_info" | grep -i "\"country_name\": \"China\"" | wc -l)

# 设置 Python 源
if [ "$is_china_ip" -eq 1 ]; then
    export PYTHON_SOURCE='https://mirrors.huaweicloud.com/python/3.12.3/Python-3.12.3.tgz'
    export PIP_SOURCE='https://pypi.tuna.tsinghua.edu.cn/simple/'
else
    export PYTHON_SOURCE='https://www.python.org/ftp/python/3.12.3/Python-3.12.3.tgz'
    export PIP_SOURCE='https://pypi.org/simple/'
fi

# 设置仓库地址
if [ "$is_china_ip" -eq 1 ]; then
    export REPOSITORY_URL='https://gitee.com/fojie/PPress.git'
else
    export REPOSITORY_URL='https://github.com/yandaozi/PPress.git'
fi

# 安装必要的工具和依赖
yum update -y
yum install -y gcc openssl-devel bzip2-devel libffi-devel zlib-devel curl git

# 安装 Python 3.12
cd /opt
wget $PYTHON_SOURCE
tar -zxvf $(basename $PYTHON_SOURCE)
cd $(basename $PYTHON_SOURCE | sed's/.tgz//')
./configure --enable-optimizations
make altinstall

# 安装 pip
python3.12 get-pip.py

# 克隆 PPress 代码
cd /opt
git clone $REPOSITORY_URL
cd PPress

# 安装 PPress 依赖
pip3.12 install -r requirements.txt -i $PIP_SOURCE

# 询问用户想要运行的端口
read -p "Please enter the port on which you want to run PPress： " PORT

# 运行 PPress
export FLASK_APP=run.py
flask run --host=0.0.0.0 --port=$PORT