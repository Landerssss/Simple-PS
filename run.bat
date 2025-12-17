@echo off
echo ========================================================
echo 正在启动 简易P图工具...
echo 首次运行需要安装依赖，请耐心等待...
echo ========================================================

:: 检查是否存在虚拟环境，不存在则创建
if not exist "venv" (
    echo 创建虚拟环境...
    python -m venv venv
)

:: 激活虚拟环境
call venv\Scripts\activate

:: 安装依赖（如果已经安装过，pip会自动跳过）
echo 正在检查并安装依赖...
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

:: 启动应用
echo.
echo 正在打开浏览器...
streamlit run app.py

pause
