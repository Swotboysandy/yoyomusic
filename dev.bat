@echo off
setlocal

echo ===================================================
echo   YoYoMusic Development Environment
echo ===================================================

:: Check if backend venv exists
if exist "backend\venv\Scripts\activate.bat" (
    echo [INFO] Starting Backend Server...
    start "YoYoMusic Backend" cmd /k "cd backend && call venv\Scripts\activate && uvicorn app.main:app --reload"
) else (
    echo [ERROR] Backend virtual environment not found!
    echo Please setup backend first:
    echo   1. cd backend
    echo   2. python -m venv venv
    echo   3. venv\Scripts\activate
    echo   4. pip install -r requirements.txt
    pause
    exit /b
)

:: Check if frontend modules exist
if exist "frontend\node_modules" (
    echo [INFO] Starting Frontend Server...
    start "YoYoMusic Frontend" cmd /k "cd frontend && npm run dev"
) else (
    echo [WARN] Frontend dependencies not found. Installing...
    start "YoYoMusic Frontend Setup" cmd /k "cd frontend && npm install && npm run dev"
)

echo.
echo Servers are starting in new windows.
echo   Backend API: http://localhost:8000/docs
echo   Frontend UI: http://localhost:3000
echo.
