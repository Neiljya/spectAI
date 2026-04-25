#!/bin/bash
cd /mnt/c/Users/siddh/Downloads/spectAI/coaching_system
source ../myenv/bin/activate
timeout 8 python3 orchestrator.py 2>&1 | tee /tmp/orch_out.txt
echo "---"
cat /tmp/orch_out.txt
