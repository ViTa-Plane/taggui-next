@echo off
cls

:: -----------------------------------------------------------------------------------------
:: System GPU & Environment Check (Windows)
:: -----------------------------------------------------------------------------------------

:: 1. Display NVIDIA Hardware Info (if available)
nvidia-smi

echo.
echo.

:: 2. Virtual Environment Configuration
:: Checks for standard virtual environment folders (.venv or venv) and displays their path
if exist "..\.venv\Scripts\activate.bat" (
    echo Virtual environment located at: %~dp0..\.venv
    call "..\.venv\Scripts\activate.bat"
) else if exist ".\.venv\Scripts\activate.bat" (
    echo Virtual environment located at: %~dp0.venv
    call ".\.venv\Scripts\activate.bat"
) else if exist "..\venv\Scripts\activate.bat" (
    echo Virtual environment located at: %~dp0..\venv
    call "..\venv\Scripts\activate.bat"
) else if exist ".\venv\Scripts\activate.bat" (
    echo Virtual environment located at: %~dp0venv
    call ".\venv\Scripts\activate.bat"
) else (
    echo Warning: Virtual environment folder not found. Running with global/system Python.
)

echo Activating virtual environment...
echo.
echo Run PyTorch ^& CUDA Verification Script
echo +-----------------------------------------------------------------------------------------+
python pytorch_cuda_check.py
echo +-----------------------------------------------------------------------------------------+

echo.
echo.
echo Done!

:: Keep terminal window open for reviewing output
cmd /k
