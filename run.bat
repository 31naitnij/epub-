@echo off
echo [1/2] 正在检查并安装必要的依赖项...
pip install -r requirements.txt

echo.
echo [2/2] 正在启动 AI EPUB 翻译工具...
python main.py

if %errorlevel% neq 0 (
    echo.
    echo 程序运行出错，请检查上方报错信息。
    pause
)
