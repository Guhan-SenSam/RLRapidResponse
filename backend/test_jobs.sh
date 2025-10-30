#!/bin/bash

# Start server in background
echo "Starting backend server..."
.venv/bin/python backend/app.py > /tmp/backend_jobs.log 2>&1 &
SERVER_PID=$!
echo "Server PID: $SERVER_PID"
sleep 5

echo "=== Testing Job Management Endpoints ==="
echo ""

# Test 1: Create and start a simple job (test script)
echo "1. Creating a test job (simple Python script)..."
JOB_RESPONSE=$(curl -s -X POST http://localhost:5000/api/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "type": "simulation",
    "command": ".venv/bin/python",
    "args": ["-c", "import time; [print(f\"Line {i}\") or time.sleep(0.5) for i in range(10)]"]
  }')
echo "$JOB_RESPONSE" | python -m json.tool
JOB_ID=$(echo "$JOB_RESPONSE" | python -c "import sys, json; print(json.load(sys.stdin).get('job_id', ''))")
echo ""

if [ -z "$JOB_ID" ]; then
  echo "Error: Failed to create job"
  kill $SERVER_PID 2>/dev/null
  exit 1
fi

echo "Job ID: $JOB_ID"
echo ""

# Test 2: List jobs
echo "2. Listing all jobs..."
curl -s http://localhost:5000/api/jobs | python -m json.tool
echo ""

# Test 3: Get job details
echo "3. Getting job details..."
curl -s "http://localhost:5000/api/jobs/$JOB_ID" | python -m json.tool | head -20
echo "   ... (truncated)"
echo ""

# Test 4: Wait a bit for output
echo "4. Waiting for job output (3 seconds)..."
sleep 3

# Test 5: Get job logs
echo "5. Getting job logs (last 20 lines)..."
curl -s "http://localhost:5000/api/jobs/$JOB_ID/logs?tail=20" | python -m json.tool
echo ""

# Test 6: Wait for completion
echo "6. Waiting for job to complete (7 seconds)..."
sleep 7

# Test 7: Check final status
echo "7. Final job status..."
curl -s "http://localhost:5000/api/jobs/$JOB_ID" | python -m json.tool | grep -E '"status"|"exit_code"'
echo ""

echo "✓ All job management tests completed!"
echo ""

# Clean up
kill $SERVER_PID 2>/dev/null
echo "Server stopped"
