cls
@echo off
cd /d "%~dp0"
@echo Hugging Face Hub is in online mode
@echo.
@echo Libraries like transformers or diffusers check online or download model weights, configuration files, 
@echo and tokenizer data to your local cache the first time you load them.
@echo you can run models and use datasets completely offline once they are saved to your local machine.
@echo.
@echo For offline, air-gap mode, use run_offline.bat
set HF_HUB_OFFLINE=0
@echo.
set ENV_DIR=.venv
@echo activate virtual environment
call .\%ENV_DIR%\Scripts\deactivate.bat
call .\%ENV_DIR%\Scripts\activate.bat

setlocal

:: Enable detailed Hugging Face logs
:: set TRANSFORMERS_VERBOSITY=info

:: Optional: also enable debug level if info isn't verbose enough
:: set TRANSFORMERS_VERBOSITY=debug

@echo start TagGUI-Next...
python main.py

endlocal
