@echo off
setlocal
set "PROJECT=%~dp0"
set "VSWHERE=%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe"

if not exist "%VSWHERE%" (
    echo ERROR: vswhere.exe not found. Install Visual Studio 2022 with C++ tools.
    goto :error
)

for /f "usebackq delims=" %%I in (`"%VSWHERE%" -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath`) do set "VSROOT=%%I"
if not defined VSROOT (
    echo ERROR: MSVC C++ tools not found.
    goto :error
)

call "%VSROOT%\Common7\Tools\VsDevCmd.bat" -arch=amd64 -host_arch=amd64
if errorlevel 1 goto :error

where cl.exe >nul 2>&1
if errorlevel 1 goto :error

cd /d "%PROJECT%"
if errorlevel 1 goto :error

where code.cmd >nul 2>&1
if errorlevel 1 (
    echo ERROR: VS Code CLI 'code' is not on PATH.
    goto :error
)

call code.cmd --new-window .
exit /b 0

:error
echo.
echo Failed to launch VS Code with the MSVC developer environment.
pause
exit /b 1
