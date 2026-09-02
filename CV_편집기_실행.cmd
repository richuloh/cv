@echo off
chcp 65001 >nul
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
  echo Python을 찾을 수 없습니다. Python 3.10 이상을 설치한 뒤 다시 실행하세요.
  pause
  exit /b 1
)
python scripts\editor_server.py
if errorlevel 1 (
  echo.
  echo 편집기를 실행하지 못했습니다. 위 오류 메시지를 확인하세요.
  pause
)
