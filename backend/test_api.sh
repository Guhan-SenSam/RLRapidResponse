#!/bin/bash

# Start server in background
.venv/bin/python backend/app.py > /tmp/backend.log 2>&1 &
SERVER_PID=$!
echo "Server PID: $SERVER_PID"
sleep 5

echo "=== Testing REST API Endpoints ==="
echo ""

echo "1. Health check:"
curl -s http://localhost:5000/api/health | python -m json.tool
echo ""

echo "2. Server info:"
curl -s http://localhost:5000/api/info | python -m json.tool
echo ""

echo "3. Create simulation:"
RESPONSE=$(curl -s -X POST http://localhost:5000/api/simulations \
  -H "Content-Type: application/json" \
  -d '{"scenario_config": {"type": "random", "num_casualties": 20}, "agent_type": "nearest_hospital"}')
echo "$RESPONSE" | python -m json.tool
SIM_ID=$(echo "$RESPONSE" | python -c "import sys, json; print(json.load(sys.stdin)['simulation_id'])")
echo ""

echo "4. List simulations:"
curl -s http://localhost:5000/api/simulations | python -m json.tool
echo ""

echo "5. Get simulation details (truncated):"
curl -s "http://localhost:5000/api/simulations/$SIM_ID" | python -m json.tool | head -25
echo "   ... (truncated)"
echo ""

echo "6. Set speed to 2x:"
curl -s -X POST "http://localhost:5000/api/simulations/$SIM_ID/speed" \
  -H "Content-Type: application/json" \
  -d '{"speed": 2.0}' | python -m json.tool
echo ""

echo "7. Delete simulation:"
curl -s -X DELETE "http://localhost:5000/api/simulations/$SIM_ID" | python -m json.tool
echo ""

echo "✓ All API tests completed!"

# Kill server
kill $SERVER_PID 2>/dev/null
