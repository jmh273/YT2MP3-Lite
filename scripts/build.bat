@echo off
setlocal enabledelayedexpansion
REM ============================================================================
REM build.bat - produce a self-contained Windows zip release of yt2mp3-lite.
REM
REM Steps:
REM   1. Compute version from `git describe --tags --abbrev=0` (strip leading v)
REM      Override by setting VERSION env var (CI passes the tag explicitly).
REM   2. Build frontend SPA (npm run build -> frontend/dist/)
REM   3. Stage SPA into backend/static/
REM   4. Run PyInstaller (yt2mp3-lite.spec -> backend/dist/yt2mp3-lite/)
REM   5. Stage ffmpeg.exe + mp3gain.exe + deno.exe + THIRD-PARTY-NOTICES.txt + update.bat
REM   6. Bundle gate (scripts/check_bundle.py), then zip ->
REM      dist/yt2mp3-lite-v<VERSION>-windows-x64.zip
REM
REM NOTE: YT2MP3-Lite needs NO Google credentials or Google API packages.
REM       The build fails if a client_secret.json or any Google API package
REM       ends up in the bundle (scripts/check_bundle.py).
REM
REM Required tools on PATH: git, node, npm, python (with pyinstaller installed)
REM Required files in tools/: ffmpeg.exe, mp3gain.exe, deno.exe
REM ============================================================================

cd /d "%~dp0\.."
set REPO_ROOT=%CD%
set BACKEND=%REPO_ROOT%\backend
set FRONTEND=%REPO_ROOT%\frontend
set TOOLS=%REPO_ROOT%\tools
set DIST=%REPO_ROOT%\dist

REM --- 1. Version ---------------------------------------------------------------
if defined VERSION (
    echo [build] Using VERSION from env: !VERSION!
) else (
    for /f "tokens=*" %%i in ('git describe --tags --abbrev^=0 2^>nul') do set TAG=%%i
    if "!TAG!"=="" (
        echo [build] No git tag found; defaulting VERSION=0.0.0-dev
        set VERSION=0.0.0-dev
    ) else (
        set VERSION=!TAG!
    )
)
REM Strip a single leading 'v' if present (so v0.5.0 becomes 0.5.0; v-only chars in version stay)
if "!VERSION:~0,1!"=="v" set VERSION=!VERSION:~1!
echo [build] VERSION=!VERSION!
> "%BACKEND%\_version.txt" echo !VERSION!

REM --- 2. Verify required bundled tools -----------------------------------------
for %%F in (ffmpeg.exe mp3gain.exe deno.exe) do (
    if not exist "%TOOLS%\%%F" (
        echo [build] ERROR: missing %TOOLS%\%%F
        echo [build] Place ffmpeg.exe, mp3gain.exe and deno.exe in tools/ before building.
        exit /b 1
    )
)

REM --- 3. Frontend build --------------------------------------------------------
REM Full build: vue-tsc type-check + vite build.
echo [build] Building frontend...
pushd "%FRONTEND%"
call npm ci || (popd & exit /b 1)
call npm run build || (popd & exit /b 1)
popd

REM Stage SPA into backend/static/
if exist "%BACKEND%\static" rmdir /s /q "%BACKEND%\static"
xcopy "%FRONTEND%\dist" "%BACKEND%\static\" /e /i /q || exit /b 1

REM --- 4. PyInstaller -----------------------------------------------------------
echo [build] Running PyInstaller...
pushd "%BACKEND%"
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
python -m PyInstaller "..\yt2mp3-lite.spec" --noconfirm --clean || (popd & exit /b 1)
popd

set BUNDLE=%BACKEND%\dist\yt2mp3-lite

REM --- 5. Stage extras into the bundle ------------------------------------------
echo [build] Staging extras...
copy /y "%TOOLS%\ffmpeg.exe"          "%BUNDLE%\" >nul || exit /b 1
copy /y "%TOOLS%\mp3gain.exe"         "%BUNDLE%\" >nul || exit /b 1
REM deno 是 yt-dlp 解 YouTube nsig challenge 的 JS runtime；缺了下載會全面 403。
copy /y "%TOOLS%\deno.exe"            "%BUNDLE%\" >nul || exit /b 1
copy /y "%REPO_ROOT%\scripts\update.bat" "%BUNDLE%\" >nul || exit /b 1
if exist "%REPO_ROOT%\THIRD-PARTY-NOTICES.txt" (
    copy /y "%REPO_ROOT%\THIRD-PARTY-NOTICES.txt" "%BUNDLE%\" >nul || exit /b 1
) else (
    echo [build] ERROR: missing %REPO_ROOT%\THIRD-PARTY-NOTICES.txt ^(GPL compliance^)
    exit /b 1
)
if exist "%REPO_ROOT%\docs\README-DEPLOY.md" (
    copy /y "%REPO_ROOT%\docs\README-DEPLOY.md" "%BUNDLE%\" >nul
)

REM --- 5b. Bundle gate: no Google credentials / Google API packages ----------
REM check_bundle.py exits 0 = clean, 1 = violation, 2 = not a valid bundle
REM (missing exe or _internal) -- an empty dir must never count as clean.
python "%REPO_ROOT%\scripts\check_bundle.py" "%BUNDLE%"
if errorlevel 1 (
    echo [build] ERROR: bundle gate failed -- refusing to package.
    exit /b 1
)

REM --- 6. Zip -------------------------------------------------------------------
if not exist "%DIST%" mkdir "%DIST%"
set ZIP=%DIST%\yt2mp3-lite-v!VERSION!-windows-x64.zip
if exist "%ZIP%" del "%ZIP%"
echo [build] Zipping -^> %ZIP%
powershell -NoProfile -Command "Compress-Archive -Path '%BUNDLE%\*' -DestinationPath '%ZIP%' -Force" || exit /b 1

echo.
echo [build] Done. Artifact: %ZIP%
for %%I in ("%ZIP%") do echo [build] Size: %%~zI bytes
exit /b 0
