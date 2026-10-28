cls
@echo off

set ENV_DIR=python_embeded
@echo activate virtual environment
call .\%ENV_DIR%\Scripts\deactivate.bat
call .\%ENV_DIR%\Scripts\activate.bat

@echo install requirements
pip install -r requirements.txt

rem keep the window open
cmd /k