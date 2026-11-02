cls
@echo off

:: -----------------------------------------------------------------------------------------
:: System GPU & Environment Check (Windows)
:: -----------------------------------------------------------------------------------------

:: 1. Display NVIDIA Hardware Info (if available)
nvidia-smi

echo.
echo.

:: 2. Virtual Environment Configuration
:: Default embedded environment folder: python_embeded
:: Note: If using a standard virtual environment (e.g., .venv or venv), update ENV_DIR below:
set ENV_DIR=python_embeded

@echo Activating virtual environment...
if exist .\%ENV_DIR%\Scripts\activate.bat (
    call .\%ENV_DIR%\Scripts\deactivate.bat 2>nul
    call .\%ENV_DIR%\Scripts\activate.bat
) else if exist .\venv\Scripts\activate.bat (
    call .\venv\Scripts\activate.bat
) else if exist .\.venv\Scripts\activate.bat (
    call .\.venv\Scripts\activate.bat
) else (
    @echo Warning: Virtual environment folder not found. Running with global/system Python.
)

:: 3. Run PyTorch & CUDA Verification Script
@ echo +-----------------------------------------------------------------------------------------+
python .\assets\pytorch_cuda_check.py
@ echo +-----------------------------------------------------------------------------------------+

echo.
echo.
@echo Done!

:: Keep terminal window open for reviewing output
cmd /k