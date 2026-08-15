@echo off
title 校园活动报名系统 - 一键启动
cd /d "%~dp0"

echo ==========================================================
echo    校园社团活动报名系统 - 一键启动
echo ==========================================================
echo.

rem ---- 前置检查：依赖是否已安装 ----
if not exist ".venv\Scripts\python.exe" (
    echo [错误] 未找到虚拟环境 .venv，请先执行：
    echo        python -m venv .venv
    echo        .venv\Scripts\activate ^&^& pip install -r requirements.txt
    pause
    exit /b 1
)
if not exist "frontend\node_modules" (
    echo [错误] 未找到前端依赖 node_modules，请先执行：
    echo        cd frontend ^&^& npm install
    pause
    exit /b 1
)

rem ---- 检查 Docker 是否在运行 ----
docker info >nul 2>&1
if errorlevel 1 (
    echo [错误] Docker 未运行，请先启动 Docker Desktop，再重新运行本脚本。
    pause
    exit /b 1
)

rem ---- 1. 启动基础设施（MySQL 3307 + RabbitMQ 5672；Redis 优先用本机的） ----
echo [1/5] 启动基础设施 ...
netstat -ano | findstr ":6379 " >nul 2>&1
if errorlevel 1 (
    echo       - Redis（6379）未运行，将连同 Redis 容器一起启动
    docker compose up -d mysql redis rabbitmq
) else (
    echo       - Redis（6379）本机已在运行，跳过 Redis 容器
    docker compose up -d mysql rabbitmq
)

rem ---- 2. 等待 MySQL 就绪（最多等 90 秒） ----
echo [2/5] 等待 MySQL 就绪 ...
set /a try=0
:wait_mysql
powershell -NoProfile -Command "if ((docker inspect --format '{{.State.Health.Status}}' ca-mysql) -eq 'healthy') { exit 0 } else { exit 1 }"
if %errorlevel%==0 goto mysql_ok
set /a try+=1
if %try% geq 30 (
    echo       [错误] MySQL 长时间未就绪，请检查 Docker 容器。
    pause
    exit /b 1
)
ping -n 4 127.0.0.1 >nul
goto wait_mysql
:mysql_ok
echo       - MySQL 就绪

rem ---- 3. 启动后端 API（8000） ----
echo [3/5] 启动后端 API（8000）...
start "后端API-8000" cmd /k "cd /d %~dp0 && .venv\Scripts\activate && uvicorn app.main:app --host 127.0.0.1 --port 8000"

rem ---- 4. 启动 Celery worker + beat ----
echo [4/5] 启动 Celery worker 与 beat ...
start "Celery-Worker" cmd /k "cd /d %~dp0 && .venv\Scripts\activate && celery -A app.tasks.celery_app.celery_app worker --loglevel=info --pool=threads --concurrency=4"
start "Celery-Beat" cmd /k "cd /d %~dp0 && .venv\Scripts\activate && celery -A app.tasks.celery_app.celery_app beat --loglevel=info"

rem ---- 5. 启动前端（5173） ----
echo [5/5] 启动前端（5173）...
start "前端-5173" cmd /k "cd /d %~dp0frontend && npm run dev"

rem ---- 等待后端就绪后打开浏览器 ----
echo.
echo 等待服务就绪，稍后自动打开浏览器...
ping -n 11 127.0.0.1 >nul
start http://localhost:5173

echo.
echo ==========================================================
echo   启动完成！已弹出 4 个服务窗口，请勿关闭。
echo   浏览器已打开 http://localhost:5173
echo   管理员账号：admin  密码：admin123456
echo   停止系统：双击「停止系统.bat」
echo ==========================================================
ping -n 7 127.0.0.1 >nul
