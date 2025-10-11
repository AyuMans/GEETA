@echo off
echo ========================================
echo    Geeta Document QA - NSSM Installer
echo ========================================
echo.

REM Check if running as administrator
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: This script must be run as Administrator!
    echo.
    echo Right-click and select "Run as administrator"
    echo.
    pause
    exit /b 1
)

echo ✅ Running as Administrator
cd /d "C:\Ayush\Development\Geeta"

echo.
echo Step 1: Removing old service if exists...
nssm remove GeetaDocumentQA confirm

echo.
echo Step 2: Installing new service...
nssm install GeetaDocumentQA "C:\Users\bhamb\AppData\Local\Programs\Python\Python313\python.exe"
nssm set GeetaDocumentQA AppParameters "-m" "streamlit" "run" "webgeeta.py" "--server.port=8501" "--server.address=0.0.0.0" "--server.headless=true" "--browser.gatherUsageStats=false"
nssm set GeetaDocumentQA AppDirectory "C:\Ayush\Development\Geeta"
nssm set GeetaDocumentQA DisplayName "Geeta Document QA System"
nssm set GeetaDocumentQA Description "Document Question Answering System for Bhagavad Geeta with Gemini AI"
nssm set GeetaDocumentQA Start SERVICE_AUTO_START
nssm set GeetaDocumentQA AppStdout "C:\Ayush\Development\Geeta\service.log"
nssm set GeetaDocumentQA AppStderr "C:\Ayush\Development\Geeta\service_error.log"

echo.
echo Step 3: Starting service...
nssm start GeetaDocumentQA

echo.
echo Step 4: Checking service status...
nssm status GeetaDocumentQA

echo.
if %errorlevel% equ 0 (
    echo 🎉 SUCCESS! Geeta Document QA Service is running!
    echo.
    echo 🌐 Access your application at: http://localhost:8501
    echo.
    echo 📋 Log files created in this folder.
) else (
    echo ❌ Service failed to start. Check service_error.log
)

echo.
pause

