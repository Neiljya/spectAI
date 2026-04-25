#!/bin/bash
# Kill any agents already running on these ports
fuser -k 8000/tcp 8001/tcp 8002/tcp 8003/tcp 2>/dev/null

cd /mnt/c/Users/siddh/Downloads/spectAI
source myenv/bin/activate

(cd coaching_system && python3 gamesense_agent.py 2>&1 | tee /tmp/gamesense.log) &
(cd coaching_system && python3 mechanics_agent.py 2>&1 | tee /tmp/mechanics.log) &
(cd coaching_system && python3 mental_agent.py   2>&1 | tee /tmp/mental.log) &
(cd coaching_system && python3 orchestrator.py   2>&1 | tee /tmp/orchestrator.log) &

echo ""
echo "All 4 agents started. Waiting for them to come online..."
sleep 6
echo ""
echo "=== Open these URLs in your browser to register each agent on Agentverse ==="
echo ""
echo "Gamesense:   https://agentverse.ai/inspect/?uri=http%3A//127.0.0.1%3A8001&address=agent1qftwnuxfh4weyqqc9pmeswmlug4vtk28fcxm7ywl6s38gxr5cf8lcy69jes"
echo "Mechanics:   https://agentverse.ai/inspect/?uri=http%3A//127.0.0.1%3A8002&address=agent1qt7afg76l48n8h60w682zr28wwt2anw2kupltl5tgv8uqzk60eh4uc29a5r"
echo "Mental:      https://agentverse.ai/inspect/?uri=http%3A//127.0.0.1%3A8003&address=agent1q28kxlqfyl60z9fap0058fh2wa7zkpd9dx3h9n6j5nu7w7656qlwyu69du0"
echo "Orchestrator:https://agentverse.ai/inspect/?uri=http%3A//127.0.0.1%3A8000&address=agent1qv3vml6d7av788k4yyhwrwssmj4tsct7z9nw8eyva9h6jc29quka5wmh6am"
echo ""
echo "Agents are running. Press Ctrl+C to stop."
wait
