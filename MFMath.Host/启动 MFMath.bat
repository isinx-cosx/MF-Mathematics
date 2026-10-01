@echo off
rem Launch the Release build (self-contained: loads UI from wwwroot via https://mfmath.local)
rem For frontend hot-reload instead use: npm run dev in MFMath.UI.Vue + the Debug build.
set "EXE=%~dp0bin\Release\net10.0-windows\MFMath.exe"
if not exist "%EXE%" (
  echo Release build not found:
  echo   %EXE%
  echo Build it first:
  echo   dotnet build "%~dp0MFMath.Host.csproj" -c Release --no-incremental
  pause
  exit /b 1
)
start "" "%EXE%"
