# RLRapidResponse Backend

Flask-based backend server for managing and visualizing mass casualty incident simulations with real-time WebSocket updates.

## Features

- **Multi-Simulation Management**: Create and manage multiple concurrent simulations
- **REST API**: Full CRUD operations for simulation control
- **WebSocket Support**: Real-time updates via Socket.IO
- **Multiple Agents**: Support for various dispatch policies (random, nearest hospital, triage priority, trauma matching)
- **Speed Control**: Adjustable playback speed (1x to 100x)
- **Thread-Safe**: Concurrent simulation support with thread-safe operations

## Architecture

```
backend/
├── app.py                          # Flask application with REST API and WebSocket
├── controllers/
│   └── simulation_manager.py       # Multi-simulation controller
├── models/                         # (Future: data models)
├── utils/                          # (Future: helper utilities)
├── requirements.txt                # Python dependencies
├── test_backend.py                # Unit tests for SimulationManager
└── test_api.sh                    # API endpoint tests
```

## Quick Start

### 1. Install Dependencies

All dependencies are managed via `uv` in the project root:

```bash
# From project root
uv pip install -r backend/requirements.txt
```

### 2. Start the Server

```bash
# From project root
.venv/bin/python backend/app.py
```

The server will start on `http://0.0.0.0:5000`

### 3. Test the Server

```bash
# Run backend unit tests
.venv/bin/python backend/test_backend.py

# Run API endpoint tests
./backend/test_api.sh
```

## REST API Endpoints

### General

- `GET /api/health` - Health check
- `GET /api/info` - Server information and available agents

### Simulation CRUD

- `POST /api/simulations` - Create new simulation
- `GET /api/simulations` - List all simulations
- `GET /api/simulations/<id>` - Get simulation details
- `DELETE /api/simulations/<id>` - Delete simulation

### Simulation Control

- `POST /api/simulations/<id>/start` - Start simulation
- `POST /api/simulations/<id>/pause` - Pause simulation
- `POST /api/simulations/<id>/resume` - Resume simulation
- `POST /api/simulations/<id>/stop` - Stop simulation
- `POST /api/simulations/<id>/speed` - Set playback speed

## API Examples

### Create a Simulation

```bash
curl -X POST http://localhost:5000/api/simulations \
  -H "Content-Type: application/json" \
  -d '{
    "scenario_config": {
      "type": "random",
      "region": "CA",
      "num_casualties": 60,
      "ambulances_per_hospital": 2,
      "field_ambulances": 5
    },
    "agent_type": "nearest_hospital"
  }'
```

**Response:**
```json
{
  "simulation_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "created",
  "success": true
}
```

### Start a Simulation

```bash
curl -X POST http://localhost:5000/api/simulations/550e8400-e29b-41d4-a716-446655440000/start
```

### List All Simulations

```bash
curl http://localhost:5000/api/simulations
```

**Response:**
```json
{
  "simulations": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "status": "running",
      "agent_type": "nearest_hospital",
      "created_at": "2025-01-01T00:00:00",
      "current_time": 45,
      "metrics": {
        "deaths": 2,
        "transported": 15,
        "casualties_waiting": 8
      }
    }
  ],
  "count": 1,
  "success": true
}
```

### Set Playback Speed

```bash
curl -X POST http://localhost:5000/api/simulations/550e8400-e29b-41d4-a716-446655440000/speed \
  -H "Content-Type: application/json" \
  -d '{"speed": 2.0}'
```

## WebSocket Events

### Client → Server

- `connect` - Establish connection
- `disconnect` - Close connection
- `subscribe` - Subscribe to simulation updates
  ```javascript
  socket.emit('subscribe', {simulation_id: '550e8400-...'})
  ```
- `unsubscribe` - Unsubscribe from simulation
  ```javascript
  socket.emit('unsubscribe', {simulation_id: '550e8400-...'})
  ```

### Server → Client

- `connection:success` - Connection established
- `subscribed` - Subscription confirmed
- `simulation:started` - Simulation started
- `simulation:timestep` - Timestep update (every simulation minute)
- `simulation:event:dispatch` - Ambulance dispatched
- `simulation:event:pickup` - Casualty picked up
- `simulation:event:delivery` - Casualty delivered to hospital
- `simulation:event:death` - Casualty death
- `simulation:paused` - Simulation paused
- `simulation:resumed` - Simulation resumed
- `simulation:stopped` - Simulation stopped
- `simulation:completed` - Simulation completed
- `simulation:error` - Simulation error

## WebSocket Example (JavaScript)

```javascript
import { io } from 'socket.io-client';

const socket = io('http://localhost:5000');

socket.on('connect', () => {
  console.log('Connected to server');
  socket.emit('subscribe', {simulation_id: '550e8400-...'});
});

socket.on('simulation:timestep', (data) => {
  console.log(`Time: ${data.time}`);
  console.log(`Casualties: ${data.casualties.length}`);
  console.log(`Ambulances: ${data.ambulances.length}`);
  console.log(`Metrics:`, data.metrics);
});

socket.on('simulation:completed', (data) => {
  console.log('Simulation completed!');
  console.log('Final metrics:', data.final_metrics);
});
```

## Available Agents

- `random` - Random dispatch policy (baseline)
- `nearest_hospital` - Dispatch to nearest hospital
- `triage_priority` - Prioritize RED > YELLOW > GREEN casualties
- `trauma_matching` - Match trauma level to hospital capability

## Scenario Configuration

### Random Scenario (Generated)

```json
{
  "type": "random",
  "region": "CA",
  "num_casualties": 60,
  "ambulances_per_hospital": 2,
  "ambulances_per_hospital_variation": 1,
  "field_ambulances": 5,
  "field_ambulance_radius_km": 10.0,
  "seed": 123
}
```

### File-Based Scenario (Pre-generated)

```json
{
  "type": "file",
  "file": "scenarios/benchmark_01.json"
}
```

## Technology Stack

- **Flask 3.0.0** - Web framework
- **Flask-SocketIO 5.3.5** - WebSocket support
- **Flask-CORS 4.0.0** - Cross-origin resource sharing
- **Gevent 25.9.1** - Async support (Python 3.13+ compatible)
- **Python-SocketIO 5.10.0** - Socket.IO protocol

## Development

### Running Tests

```bash
# Backend unit tests
.venv/bin/python backend/test_backend.py

# API integration tests
./backend/test_api.sh
```

### Debug Mode

The server runs in debug mode by default. To disable:

```python
# In app.py, change:
socketio.run(app, host='0.0.0.0', port=5000, debug=False)
```

### Logging

Logs are written to console with the following format:
```
2025-01-01 12:00:00 - module_name - INFO - Log message
```

To change log level:
```python
logging.basicConfig(level=logging.DEBUG)
```

## Troubleshooting

### Port Already in Use

```bash
# Find process using port 5000
lsof -i :5000

# Kill the process
kill -9 <PID>
```

### Import Errors

Make sure you're using the project's virtual environment:

```bash
# Activate virtual environment
source .venv/bin/activate  # Linux/Mac
.venv\Scripts\activate     # Windows

# Or use uv directly
uv pip install -r backend/requirements.txt
```

### Python 3.13 Compatibility

We use `gevent` instead of `eventlet` for Python 3.13+ compatibility. If you encounter issues, ensure gevent is installed:

```bash
uv pip install gevent gevent-websocket
```

## Production Deployment

For production, consider:

1. **Use a production WSGI server** (gunicorn with gevent workers)
   ```bash
   gunicorn --worker-class gevent -w 4 'backend.app:app' -b 0.0.0.0:5000
   ```

2. **Use environment variables for configuration**
3. **Enable HTTPS/WSS** for secure connections
4. **Set up proper logging** (file-based, log rotation)
5. **Add authentication** for API endpoints
6. **Configure CORS** for specific origins only
7. **Add rate limiting** to prevent abuse

## License

Part of the RLRapidResponse project - College RL project for optimizing MCI response.
