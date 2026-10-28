cls
@echo off
rem set FIFTYONE_DIR=%~dp0
rem set ENV_DIR=venv
set ENV_DIR=python_embeded

if exist %ENV_DIR% (
  @echo python embeded is already installed,exit now...
  GOTO :end
)

@echo Installing Python virtual environment to %ENV_DIR%
python -m venv %ENV_DIR%

rem activate virtual environment
call .\%ENV_DIR%\Scripts\deactivate.bat
call .\%ENV_DIR%\Scripts\activate.bat

@echo update pip...
python.exe -m pip install --upgrade pip



:end
rem keep the window open
cmd /k