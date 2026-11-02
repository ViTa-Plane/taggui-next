#!/usr/bin/env bash
clear

# Check for NVIDIA system tools (Linux/Windows WSL)
if command -v nvidia-smi &> /dev/null; then
    nvidia-smi
elif command -v system_profiler &> /dev/null; then
    echo "Checking hardware profile (macOS)..."
    system_profiler SPHardwareDataType
else
    echo "No standard GPU profiling tool found (nvidia-smi / system_profiler)."
fi

echo ""
echo ""

# Define environment directory (adjust if using a standard .venv folder instead)
ENV_DIR="python_embeded"

echo "Activating virtual environment..."

# Handle Unix activation path (.venv/bin/activate or embedded python_embeded/bin/activate)
if [ -f "./${ENV_DIR}/bin/activate" ]; then
    source "./${ENV_DIR}/bin/activate"
elif [ -f "./venv/bin/activate" ]; then
    source "./venv/bin/activate"
else
    echo "Warning: Virtual environment not found at ./${ENV_DIR} or ./venv. Running with system python."
fi

echo "+-----------------------------------------------------------------------------------------+"
python ./assets/pytorch_cuda_check.py
echo "+-----------------------------------------------------------------------------------------+"

echo ""
echo ""
echo "Done!"