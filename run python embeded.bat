cls
@echo off

set ENV_DIR=.venv
@echo activate virtual environment
call .\%ENV_DIR%\Scripts\deactivate.bat
call .\%ENV_DIR%\Scripts\activate.bat

rem keep the window open
cmd /k