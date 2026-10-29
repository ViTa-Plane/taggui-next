cls
@echo off

set ENV_DIR=python_embeded
@echo activate virtual environment
call .\%ENV_DIR%\Scripts\deactivate.bat
call .\%ENV_DIR%\Scripts\activate.bat

@echo start TagGUI Next
main.py