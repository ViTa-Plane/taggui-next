import torch

print(f"PyTorch Version       : {torch.__version__}")
print(f"CUDA Available        : {torch.cuda.is_available()}")

if torch.cuda.is_available():
    print(f"CUDA Device Name      : {torch.cuda.get_device_name(0)}")
    try:
        cuda_tensor = torch.zeros(1).cuda()
        print(f"CUDA Test Tensor      : {cuda_tensor}")
    except Exception as e:
        print(f"CUDA Tensor Test Error: {e}")

elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
    print("Apple Silicon MPS     : Available (Mac Hardware Acceleration)")
    try:
        mps_tensor = torch.zeros(1).to("mps")
        print(f"MPS Test Tensor       : {mps_tensor}")
    except Exception as e:
        print(f"MPS Tensor Test Error : {e}")

else:
    print("Hardware Accelerator  : None found. Running on CPU.")
    cpu_tensor = torch.zeros(1)
    print(f"CPU Test Tensor       : {cpu_tensor}")