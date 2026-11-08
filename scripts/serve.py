"""Recipe wrapper: pinned upstream server, with direct CUDA loading on GB10."""
import os
import sys

import torch
from transformers import AutoModel

torch.set_num_threads(8)
model = AutoModel.from_pretrained('/model', trust_remote_code=True, dtype=torch.bfloat16,
                                 attn_implementation='sdpa', device_map='cuda').eval()
assert all(parameter.device.type == 'cuda' for parameter in model.parameters())
sys.path.insert(0, '/model')
from server_kanana_v_decide import Decider, SystemOneServer

server = SystemOneServer(('127.0.0.1', int(os.environ.get('KANANA_PORT', '18889'))),
                         Decider(model, 'kanana-2-v-decide-3b-2611'),
                         os.environ.get('DECISION_API_KEY') or None)
print(f'READY http://127.0.0.1:{server.server_port}/v1/systemone', flush=True)
try:
    server.serve_forever()
finally:
    server.server_close()
