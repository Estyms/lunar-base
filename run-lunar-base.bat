@echo off
setlocal
cd /d "%~dp0"

if not exist .venv (
    echo Virtual environment not found. Run setup.bat first.
    exit /b 1
)

call .venv\Scripts\activate.bat
echo.
echo === Lunar Base ===
echo Open http://127.0.0.1:8888 in your browser. Ctrl+C to stop.
echo.
python -m uvicorn web.app:app --host 127.0.0.1 --port 8888
endlocal
