@echo off
title 校园活动报名系统 - 停止
cd /d "%~dp0"

echo ==========================================================
echo    校园社团活动报名系统 - 停止所有服务
echo ==========================================================
echo.

echo [1/2] 停止后端 / 前端 / Celery 进程 ...
powershell -NoProfile -Command "$ErrorActionPreference='SilentlyContinue'; $ports=8000,5173; Get-NetTCPConnection -State Listen | Where-Object { $_.LocalPort -in $ports } | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }; Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'celery.*app.tasks.celery_app' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }; Write-Output '       - 进程已停止'"

echo [2/2] 停止 Docker 容器（MySQL / Redis / RabbitMQ）...
docker compose down

echo.
echo 全部已停止。要重新启动，双击「启动系统.bat」。
ping -n 5 127.0.0.1 >nul
