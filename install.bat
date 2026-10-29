cls
@echo off
set ENV_DIR=python_embeded

if exist %ENV_DIR% (
  @echo python embeded is already installed
  GOTO :skip
)

@echo Installing Python virtual environment to %ENV_DIR%
python -m venv %ENV_DIR%

:skip
rem activate virtual environment
call .\%ENV_DIR%\Scripts\deactivate.bat
call .\%ENV_DIR%\Scripts\activate.bat

@echo update pip...
python.exe -m pip install --upgrade pip

@echo install requirements
pip install -r requirements.txt

@echo off
@echo ---------------------------
@echo Done!
rem keep the window open
cmd /k