import torch
print("cuda.is_available :" ,torch.cuda.is_available())
print("cuda device       :", torch.zeros(1).cuda())
