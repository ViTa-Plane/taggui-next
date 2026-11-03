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

 if exist ..\.venv\Scripts\activate.bat (
    call ..\.venv\Scripts\activate.bat
) else if exist .\.venv\Scripts\activate.bat (
    call .\.venv\Scripts\activate.bat
) else (
    @echo Warning: Virtual environment folder not found. Running with global/system Python.
)

@echo Activating virtual environment...
@echo
@echo Run PyTorch ^& CUDA Verification Script
@ echo +-----------------------------------------------------------------------------------------+
python pytorch_cuda_check.py
@ echo +-----------------------------------------------------------------------------------------+

echo.
echo.
@echo Done!

:: Keep terminal window open for reviewing output
cmd /k