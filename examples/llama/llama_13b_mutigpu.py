import torch
import os
import sys
sys.path.append('/share/project/liuguang/flagai-internal')
import argparse
from flagai import mpu
from flagai.auto_model.auto_loader import AutoLoader
import random
import numpy as np
from flagai.model.predictor.predictor import Predictor
from pathlib import Path 

os.environ["ENV_TYPE"] = "deepspeed+mpu"
model_parallel_size = 4
world_size = 4

os.environ["MODEL_PARALLEL_SIZE"] = str(model_parallel_size)
os.environ["WORLD_SIZE"] = str(world_size)

def set_random_seed(seed):
    """Set random seed for reproducability."""
    if seed is not None and seed > 0:
        random.seed(seed)
        np.random.seed(seed)
        torch.manual_seed(seed)
        mpu.model_parallel_cuda_manual_seed(seed)

parser = argparse.ArgumentParser()
parser.add_argument('--local_rank',
                    type=int,
                    default=0,
                    help="local_rank")

ds_args = parser.parse_args()
local_rank = ds_args.local_rank


master_addr = os.environ.get('MASTER_ADDR', '127.0.0.1')
master_port = os.environ.get('MASTER_PORT', '17501')

device = torch.device("cuda", local_rank)

def initialize_distributed():
    """Initialize torch.distributed."""
    # Manually set the device ids.
    torch.cuda.set_device(device)
    # Call the init process
    init_method = 'tcp://'

    init_method += master_addr + ':' + master_port
    torch.distributed.init_process_group(
        backend='nccl',  # gloo
        world_size=world_size,
        rank=local_rank,
        init_method=init_method)
    mpu.initialize_model_parallel(model_parallel_size)

initialize_distributed()

set_random_seed(123)

print(f"building model...")
loader = AutoLoader("lm", model_dir = '/share/project/liuguang/LMContinualPretrain/current_training_v1/checkpoints', model_name="llama-30b-en",max_seq_len=200, use_cache=True, max_batch_size=4, fp16=True)
model = loader.get_model()
# tokenizer = loader.get_tokenizer()
from flagai.data.tokenizer import Tokenizer
tokenizer = Tokenizer.from_pretrained("llama-30b-en",cache_dir="/share/project/liuguang/llama/gpt2_new_1w") 
model.eval()
model.to(device)

torch.distributed.barrier(group=mpu.get_model_parallel_group())

text = """The capital of Germany is the city of """

predictor = Predictor(model, tokenizer)
out = predictor.predict_generate_randomsample(text, out_max_length=200,top_p=0.95)
if mpu.get_model_parallel_rank() == 0:
    print(f"pred is {out}")


