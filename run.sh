#!/bin/bash

# 确保脚本在出错时停止
set -e

echo "[1/2] 正在检查并安装必要的依赖项..."
# 使用 python3，因为 macOS 默认可能包含 python2 或需要显式指定 python3
python3 -m pip install -r requirements.txt

echo ""
echo "[2/2] 正在启动 AI EPUB 翻译工具..."
python3 main.py

if [ $? -ne 0 ]; then
    echo ""
    echo "程序运行出错，请检查上方报错信息。"
    read -p "按任意键退出..."
fi
