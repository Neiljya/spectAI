#!/bin/bash
source /mnt/c/Users/siddh/Downloads/spectAI/myenv/bin/activate
python3 -c "from uagents import Agent; import inspect; print(inspect.signature(Agent.__init__))"
