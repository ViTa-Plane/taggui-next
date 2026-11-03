#!/usr/bin/env bash
clear

# Get the absolute directory where this script actually lives
SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"

# Strip Windows drive letters (e.g., E:/GitHub/ -> /GitHub/) for native Linux/Git Bash compatibility
if [[ "$SCRIPT_DIR" =~ ^[A-Za-z]:/ ]]; then
    SCRIPT_DIR="${SCRIPT_DIR:2}"
fi

# Ensure it starts with a proper root slash
if [[ "$SCRIPT_DIR" != /* ]]; then
    SCRIPT_DIR="/$SCRIPT_DIR"
fi

# Check for NVIDIA system tools
if command -v nvidia-smi &> /dev/null; then
    nvidia-smi
else
    echo "No standard GPU profiling tool found (nvidia-smi)."
fi

echo ""
echo ""
echo "Searching for virtual environment..."

# Walk up directories from the script location to find .venv
CURRENT_LOOKUP="$SCRIPT_DIR"
VENV_PATH=""

while [[ "$CURRENT_LOOKUP" != "/" && -n "$CURRENT_LOOKUP" ]]; do
    # Check for Windows-style 'Scripts/activate' first, then Linux 'bin/activate'
    if [ -f "$CURRENT_LOOKUP/.venv/Scripts/activate" ]; then
        VENV_PATH="$CURRENT_LOOKUP/.venv/Scripts/activate"
        break
    elif [ -f "$CURRENT_LOOKUP/.venv/bin/activate" ]; then
        VENV_PATH="$CURRENT_LOOKUP/.venv/bin/activate"
        break
    fi
    CURRENT_LOOKUP="$(dirname "$CURRENT_LOOKUP")"
done

# Activate the environment if found
if [ -n "$VENV_PATH" ] && [ -f "$VENV_PATH" ]; then
    echo "Activating virtual environment at: $VENV_PATH"
    source "$VENV_PATH"
else
    echo "Warning: Could not find .venv/Scripts/activate or .venv/bin/activate in parent directories."
    echo "Running with system python."
fi

echo "+-----------------------------------------------------------------------------------------+"
# Safely run the python file assuming it's in the same folder as the script or in assets
if [ -f "$SCRIPT_DIR/pytorch_cuda_check.py" ]; then
    python "$SCRIPT_DIR/pytorch_cuda_check.py"
elif [ -f "$SCRIPT_DIR/assets/pytorch_cuda_check.py" ]; then
    python "$SCRIPT_DIR/assets/pytorch_cuda_check.py"
else
    python pytorch_cuda_check.py
fi
echo "+-----------------------------------------------------------------------------------------+"

echo ""
echo ""
echo "Done!"
read -p "Press any key to continue" x
