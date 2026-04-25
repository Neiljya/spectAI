#!/bin/bash
source /mnt/c/Users/siddh/Downloads/spectAI/myenv/bin/activate
python3 -c "
import inspect
from uagents import Agent
src = inspect.getsourcefile(Agent)
print('Source file:', src)
"
# find where agentverse param is processed
python3 -c "
import uagents
import os
pkg_dir = os.path.dirname(uagents.__file__)
print(pkg_dir)
"
