cls
@echo off

nvidia-smi


echo.
echo.
set ENV_DIR=python_embeded
@echo activate virtual environment
call .\%ENV_DIR%\Scripts\deactivate.bat
call .\%ENV_DIR%\Scripts\activate.bat
@ echo +-----------------------------------------------------------------------------------------+
.\assets\pytorch_cuda_check.py
@ echo +-----------------------------------------------------------------------------------------+
echo.
echo.
@echo Done!
rem keep the window open
cmd /k