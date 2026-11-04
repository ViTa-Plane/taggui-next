#!/bin/bash

# -----------------------------------------------------------------------------------------
# System GPU & Environment Check (Cross-Platform Bash)
# -----------------------------------------------------------------------------------------

# 1. Display Hardware Info
if command -v nvidia-smi &> /dev/null; then
    nvidia-smi
elif [[ "$OSTYPE" == "darwin"* ]]; then
    echo "--- macOS Hardware Info ---"
    system_profiler SPDisplaysDataType | grep -E "Chipset Model|VRAM"
else
    echo "nvidia-smi not found. Non-NVIDIA Linux or integrated graphics system."
fi

echo -e "\n\n"

# Helper function to resolve absolute system paths cleanly
print_venv_path() {
    local relative_path=$1
    if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" ]]; then
        echo "Virtual environment located at: $(pwd -W)/$relative_path"
    else
        echo "Virtual environment located at: $(cd "$relative_path" && pwd)"
    fi
}

# 2. Virtual Environment Configuration
# Scans sibling and local directories, detecting both Linux 'bin' and Windows 'Scripts' folders
if [ -f "../.venv/Scripts/activate" ]; then
    print_venv_path "../.venv"
    source ../.venv/Scripts/activate
elif [ -f "../.venv/bin/activate" ]; then
    print_venv_path "../.venv"
    source ../.venv/bin/activate
elif [ -f "../venv/Scripts/activate" ]; then
    print_venv_path "../venv"
    source ../venv/Scripts/activate
elif [ -f "../venv/bin/activate" ]; then
    print_venv_path "../venv"
    source ../venv/bin/activate
elif [ -f "./.venv/Scripts/activate" ]; then
    print_venv_path ".venv"
    source ./.venv/Scripts/activate
elif [ -f "./.venv/bin/activate" ]; then
    print_venv_path ".venv"
    source ./.venv/bin/activate
else
    echo "Warning: Virtual environment folder not found. Running with global/system Python."
fi

echo -e "\nRun PyTorch & CUDA/MPS Verification Script"
echo "+-----------------------------------------------------------------------------------------+"
if command -v python3 &> /dev/null; then
    python3 pytorch_cuda_check.py
else
    python pytorch_cuda_check.py
fi
echo "+-----------------------------------------------------------------------------------------+"

echo -e "\n\nDone!"

# Keep terminal open
$SHELL
