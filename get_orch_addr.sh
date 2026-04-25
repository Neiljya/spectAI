#!/bin/bash
fuser -k 8000/tcp 2>/dev/null
sleep 1
cd /mnt/c/Users/siddh/Downloads/spectAI/coaching_system
source ../myenv/bin/activate
python3 - <<'EOF'
from uagents import Agent
a = Agent(name="orchestrator", seed="spectai_orchestrator_siddharth_2026")
print("NEW ORCHESTRATOR ADDRESS:", a.address)
EOF
