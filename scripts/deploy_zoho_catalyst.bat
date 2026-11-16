@echo off
REM ==============================================================================
REM PLUTO vProctor — Zoho Catalyst Automated Deployment Script (Windows)
REM ==============================================================================

echo [PLUTO vProctor] Initializing Zoho Catalyst Deployment...

REM 1. Detect Catalyst CLI (Global catalyst or npx zcatalyst-cli)
set CATALYST_CMD=catalyst
where catalyst >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [PLUTO vProctor] 'catalyst' not found in PATH. Using 'npx --yes zcatalyst-cli'...
    set CATALYST_CMD=npx --yes zcatalyst-cli
)

REM 2. Verify Authentication
call %CATALYST_CMD% whoami >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [AUTHENTICATION REQUIRED] You are not currently logged in to Zoho Catalyst.
    echo Please authenticate by executing:
    echo     %CATALYST_CMD% login
    echo Or if logging in to India Data Center (ap-south-1):
    echo     %CATALYST_CMD% login --dc in
    echo After logging in, re-run this script to execute deployment.
    exit /b 1
)

REM 3. Build Frontend Distribution
echo [PLUTO vProctor] Building Frontend Production SPA...
cd /d "%~dp0..\frontend"
call npm install
call npm run build
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Frontend build failed.
    exit /b 1
)
cd /d "%~dp0.."

REM 4. Validate Deployment Package
echo [PLUTO vProctor] Validating Deployment Package...
call backend\.venv\Scripts\python.exe scripts\validate_deployment_package.py
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Deployment validation failed.
    exit /b 1
)

REM 5. Deploy AppSail and Client Hosting
echo [PLUTO vProctor] Deploying AppSail and Web Client to Zoho Catalyst...
call %CATALYST_CMD% deploy --only appsail,client

echo [PLUTO vProctor] Deployment Completed Successfully!
echo Inspect live logs via: %CATALYST_CMD% appsail:logs --name pluto-backend
