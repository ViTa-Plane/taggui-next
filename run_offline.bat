cls
@echo off
cd /d "%~dp0"
@echo Hugging Face Hub is in offline mode (Downloading new VLM models will fail)
@echo use normal mode with run.bat if you have no Hugging Face VLM's installed/ first use
set HF_HUB_OFFLINE=1
@echo.
set ENV_DIR=.venv
@echo activate virtual environment
call .\%ENV_DIR%\Scripts\deactivate.bat
call .\%ENV_DIR%\Scripts\activate.bat

@echo Starting TagGUI-Next...
python main.py

@echo restore online mode...
set HF_HUB_OFFLINE=0