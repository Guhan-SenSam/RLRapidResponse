# RLRapidResponse - Mass Casualty RL Simulator

RL-based simulator to optimize ambulance dispatch during mass casualty incidents (MCI) to minimize patient deaths.

## Project Management

**Package Manager**: [uv](https://docs.astral.sh/uv/) - Fast Python package and project manager

### Setup Instructions
```bash
# Install dependencies (creates .venv automatically)
uv sync

# Activate virtual environment
source .venv/bin/activate  # Linux/Mac
# OR
.venv\Scripts\activate     # Windows

# Run scripts
uv run python simulator/train.py
uv run python simulator/evaluate.py
```

### Adding Dependencies
```bash
# Add a new package
uv add package-name

# Add development dependency
uv add --dev package-name

# Add with specific version
uv add "package-name>=1.0.0"
```

**IMPORTANT**: All heavy packages (PyTorch, TensorFlow, Stable-Baselines3) are installed only inside the project's virtual environment (`.venv/`) managed by uv. Never install globally.

## Project Structure
```
RLRapidResponse/
├── CLAUDE.md                   # This file
├── datasets/
│   └── us_hospital_locations.csv  # Hospital data (location, beds, trauma level, helipad)
├── simulator/                  # Core RL simulator (standalone)
│   ├── environment/
│   │   ├── mci_env.py         # Gymnasium environment (MCIResponseEnv)
│   │   ├── scenario_generator.py  # Generate random MCI scenarios
│   │   ├── patient_model.py   # Markov deterioration model
│   │   └── routing.py         # OSMnx routing utilities
│   ├── agents/
│   │   ├── baselines.py       # Heuristic policies (nearest, triage-priority, etc.)
│   │   └── ppo_agent.py       # Trained PPO agent wrapper
│   ├── simulation_engine.py   # Core simulator (runs independently)
│   ├── train.py               # Training script
│   └── evaluate.py            # Evaluation script
├── backend/                    # Flask API + WebSocket server
│   ├── app.py                 # Main Flask app
│   ├── simulation_controller.py  # Control simulator (start/stop/pause)
│   ├── websocket_handler.py  # Socket.IO for live updates
│   └── requirements.txt       # flask, flask-socketio, flask-cors
└── frontend/                   # React + Leaflet visualization
    ├── src/
    │   ├── components/
    │   │   ├── SimulationMap.jsx      # Live map with ambulances/casualties
    │   │   ├── SimulationControls.jsx # Start/stop/pause/speed controls
    │   │   ├── MetricsDashboard.jsx   # Real-time KPIs
    │   │   ├── CasualtyList.jsx       # List of casualties with status
    │   │   └── AmbulanceStatus.jsx    # Ambulance fleet status
    │   ├── hooks/
    │   │   └── useWebSocket.js        # WebSocket connection hook
    │   └── services/
    │       └── api.js                 # API client (axios)
    └── package.json
```

---

## Visualization & Control System Architecture

### Design Principles
1. **Simulator Independence**: Core simulator runs standalone (CLI mode) without any web dependencies
2. **Optional Visualization**: Backend/Frontend only for live visualization and control
3. **Real-time Updates**: WebSocket connection streams simulation state every timestep (1 min sim time)
4. **Separation of Concerns**: Simulator → Backend → Frontend (unidirectional data flow)

### System Components

#### 1. Core Simulator (Standalone Python)
**Purpose**: Run simulations independently, no web dependencies

**Key Features**:
- Runs from CLI: `python simulator/simulation_engine.py --scenario random --agent ppo`
- Emits events via event bus (observer pattern) that backend can optionally subscribe to
- Saves results to JSON/CSV for later analysis
- No knowledge of Flask/WebSocket (pure Python)

**Event Bus Interface**:
```python
class SimulationEngine:
    def __init__(self):
        self.event_listeners = []  # Optional listeners (e.g., WebSocket handler)

    def register_listener(self, callback):
        self.event_listeners.append(callback)

    def emit_event(self, event_type, data):
        for listener in self.event_listeners:
            listener(event_type, data)

    def step(self):
        # Update simulation
        self.emit_event('timestep', {
            'time': self.current_time,
            'casualties': self.get_casualty_states(),
            'ambulances': self.get_ambulance_states(),
            'hospitals': self.get_hospital_states(),
            'metrics': self.get_current_metrics()
        })
```

#### 2. Flask Backend (API + WebSocket Server)
**Purpose**: Control simulator and stream live updates to frontend

**Dependencies**: `flask`, `flask-socketio`, `flask-cors`, `eventlet` (or `gevent`)

**REST API Endpoints**:
```python
# Control
POST   /api/simulation/start          # Start new simulation (params: scenario_id, agent_type, speed)
POST   /api/simulation/stop           # Stop current simulation
POST   /api/simulation/pause          # Pause simulation
POST   /api/simulation/resume         # Resume simulation
POST   /api/simulation/set-speed      # Change playback speed (1x, 2x, 5x, 10x)

# Query
GET    /api/simulation/status         # Current simulation state (running/paused/stopped)
GET    /api/simulation/history        # Past simulation runs
GET    /api/scenarios                 # Available scenarios (pre-generated or random)
GET    /api/agents                    # Available agents (baselines, trained PPO)

# Data
GET    /api/hospitals                 # Hospital data (existing endpoint)
```

**WebSocket Events** (Socket.IO):
```javascript
// Server → Client
'simulation:started'    → { scenario_id, agent_type, initial_state }
'simulation:timestep'   → { time, casualties, ambulances, hospitals, metrics }
'simulation:action'     → { ambulance_id, casualty_id, hospital_id, reason }
'simulation:ended'      → { final_metrics, summary }
'simulation:error'      → { error_message }

// Client → Server
'connect'               → Establish connection
'disconnect'            → Close connection
```

**Backend Implementation**:
```python
# backend/app.py
from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit
from flask_cors import CORS
from simulation_controller import SimulationController

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

controller = SimulationController(socketio)

@app.route('/api/simulation/start', methods=['POST'])
def start_simulation():
    params = request.json
    result = controller.start(
        scenario_id=params.get('scenario_id', 'random'),
        agent_type=params.get('agent_type', 'ppo'),
        speed=params.get('speed', 1)
    )
    return jsonify(result)

@socketio.on('connect')
def handle_connect():
    print('Client connected')
    emit('connection:success', {'status': 'connected'})

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000)
```

**Simulation Controller**:
```python
# backend/simulation_controller.py
import threading
from simulator.simulation_engine import SimulationEngine

class SimulationController:
    def __init__(self, socketio):
        self.socketio = socketio
        self.engine = None
        self.running = False
        self.thread = None

    def start(self, scenario_id, agent_type, speed):
        if self.running:
            return {'error': 'Simulation already running'}

        self.engine = SimulationEngine(scenario_id, agent_type)
        self.engine.register_listener(self._on_simulation_event)
        self.speed = speed
        self.running = True

        # Run simulation in background thread
        self.thread = threading.Thread(target=self._run_simulation)
        self.thread.start()

        return {'status': 'started', 'scenario_id': scenario_id}

    def _run_simulation(self):
        while self.running and not self.engine.is_done():
            self.engine.step()
            time.sleep(1.0 / self.speed)  # Adjust speed (1x = 1 sec per sim minute)

        self.running = False
        self.socketio.emit('simulation:ended', self.engine.get_final_metrics())

    def _on_simulation_event(self, event_type, data):
        # Forward simulator events to WebSocket
        self.socketio.emit(f'simulation:{event_type}', data)
```

#### 3. React Frontend (Visualization UI)
**Purpose**: Display live simulation on map with controls

**Tech Stack**: React, Leaflet, Socket.IO-client, Axios, Tailwind CSS (or MUI)

**Key Components**:

**SimulationMap.jsx**: Main map showing real-time positions
```jsx
import { MapContainer, TileLayer, Marker, Polyline } from 'react-leaflet';
import { useWebSocket } from '../hooks/useWebSocket';

export default function SimulationMap() {
  const { casualties, ambulances, hospitals } = useWebSocket();

  return (
    <MapContainer center={[34.05, -118.25]} zoom={10}>
      <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />

      {/* Hospitals (blue) */}
      {hospitals.map(h => <Marker key={h.id} position={[h.lat, h.lon]} icon={hospitalIcon} />)}

      {/* Casualties (red/yellow/green based on triage) */}
      {casualties.map(c => <Marker key={c.id} position={[c.lat, c.lon]} icon={getCasualtyIcon(c.triage)} />)}

      {/* Ambulances with routes */}
      {ambulances.map(a => (
        <>
          <Marker key={a.id} position={[a.lat, a.lon]} icon={ambulanceIcon} />
          {a.route && <Polyline positions={a.route} color="blue" />}
        </>
      ))}
    </MapContainer>
  );
}
```

**SimulationControls.jsx**: Start/stop/pause controls
```jsx
export default function SimulationControls() {
  const [status, setStatus] = useState('stopped');
  const [speed, setSpeed] = useState(1);

  const handleStart = async () => {
    const response = await api.post('/simulation/start', {
      scenario_id: 'random',
      agent_type: 'ppo',
      speed: speed
    });
    setStatus('running');
  };

  return (
    <div className="controls">
      <button onClick={handleStart} disabled={status === 'running'}>Start</button>
      <button onClick={handlePause}>Pause</button>
      <button onClick={handleStop}>Stop</button>
      <select value={speed} onChange={(e) => setSpeed(e.target.value)}>
        <option value={1}>1x</option>
        <option value={2}>2x</option>
        <option value={5}>5x</option>
        <option value={10}>10x</option>
      </select>
    </div>
  );
}
```

**MetricsDashboard.jsx**: Real-time KPIs
```jsx
export default function MetricsDashboard() {
  const { metrics } = useWebSocket();

  return (
    <div className="metrics-grid">
      <MetricCard label="Elapsed Time" value={`${metrics.elapsed_time} min`} />
      <MetricCard label="Casualties Waiting" value={metrics.casualties_waiting} color="orange" />
      <MetricCard label="Deaths" value={metrics.deaths} color="red" />
      <MetricCard label="Transported" value={metrics.transported} color="green" />
      <MetricCard label="Avg Response Time" value={`${metrics.avg_response_time.toFixed(1)} min`} />
    </div>
  );
}
```

**useWebSocket.js**: Custom hook for WebSocket connection
```javascript
import { useEffect, useState } from 'react';
import io from 'socket.io-client';

export function useWebSocket() {
  const [socket, setSocket] = useState(null);
  const [casualties, setCasualties] = useState([]);
  const [ambulances, setAmbulances] = useState([]);
  const [hospitals, setHospitals] = useState([]);
  const [metrics, setMetrics] = useState({});

  useEffect(() => {
    const newSocket = io('http://localhost:5000');
    setSocket(newSocket);

    newSocket.on('simulation:timestep', (data) => {
      setCasualties(data.casualties);
      setAmbulances(data.ambulances);
      setHospitals(data.hospitals);
      setMetrics(data.metrics);
    });

    newSocket.on('simulation:ended', (data) => {
      console.log('Simulation ended:', data);
    });

    return () => newSocket.close();
  }, []);

  return { casualties, ambulances, hospitals, metrics, socket };
}
```

### Data Flow

```
┌─────────────────────────────────────────────────────────┐
│                    Core Simulator                       │
│  (Runs independently, no web dependencies)              │
│                                                          │
│  • MCIEnvironment (Gym)                                 │
│  • ScenarioGenerator                                    │
│  • PatientModel (deterioration)                         │
│  • PPO Agent                                            │
│  • Event Bus (emits events)                             │
└────────────────┬────────────────────────────────────────┘
                 │
                 │ Event callbacks (optional)
                 ▼
┌─────────────────────────────────────────────────────────┐
│              Flask Backend (Port 5000)                  │
│                                                          │
│  REST API ◄────────────► Simulation Controller          │
│                                 │                        │
│  Socket.IO ◄────────────────────┘                       │
│  (Broadcasts events)                                    │
└────────────────┬────────────────────────────────────────┘
                 │
                 │ WebSocket (Socket.IO)
                 ▼
┌─────────────────────────────────────────────────────────┐
│            React Frontend (Port 3000)                   │
│                                                          │
│  • useWebSocket hook (receives live updates)            │
│  • SimulationMap (Leaflet)                              │
│  • Controls (start/stop/pause)                          │
│  • Metrics Dashboard                                    │
└─────────────────────────────────────────────────────────┘
```

### Usage Modes

**Mode 1: Standalone (No UI)**
```bash
# Training
python simulator/train.py --scenarios 500 --timesteps 1000000

# Evaluation
python simulator/evaluate.py --agent ppo --num-scenarios 100 --output results.csv

# Single simulation run
python simulator/simulation_engine.py --scenario random --agent ppo --output sim.json
```

**Mode 2: Live Visualization**
```bash
# Terminal 1: Start backend
cd backend
python app.py  # Runs on port 5000

# Terminal 2: Start frontend
cd frontend
npm run dev    # Runs on port 3000

# Open browser: http://localhost:3000
# Click "Start Simulation" to see live visualization
```

### Implementation Priority (for Phase 4)

**Week 20: Core Simulator Refactoring**
- Refactor existing code to use event bus pattern
- Ensure simulator runs independently
- Add CLI interface for standalone runs

**Week 21: Backend WebSocket**
- Implement Flask-SocketIO server
- Create SimulationController with threading
- Test WebSocket events with Postman/CLI client

**Week 22: Frontend Visualization**
- Create SimulationMap component (reuse existing HospitalMap)
- Implement useWebSocket hook
- Add SimulationControls and MetricsDashboard
- Connect to backend and test live updates

---

## COLLEGE PROJECT SCOPE (2 Semesters / 26 Weeks)

### Core Design
- **Single Master Agent**: One centralized PPO agent controls all ambulance dispatch (not multi-agent)
- **Scale**: 5-10 ambulances, 8-10 hospitals, 50-80 casualties per scenario
- **Triage**: START system (Red/Yellow/Green/Black)
- **Routing**: OpenStreetMap (OSMnx) - real roads, NO traffic simulation
- **Training**: 500 scenarios, PPO (Stable-Baselines3), 1-2M timesteps (~30-50 hours GPU)
- **Goal**: ≥10% mortality reduction vs. nearest-hospital baseline

### Excluded (Future Work)
- ❌ Field trauma center, hospital agents, crew fatigue, traffic, multi-agent, inter-hospital transfers

---

## Implementation Phases

### Phase 1: Environment (Weeks 1-6)
**Build simulator without RL**
1. **Data & Maps**: Load hospitals from CSV, integrate OSMnx for selected region
2. **Scenario Generator**: Random MCI locations, 50-80 casualties with realistic triage distribution (25% Red, 40% Yellow, 30% Green, 5% Black)
3. **Patient Model**: Markov deterioration (Red: 5%/min → Death, Yellow: 1%/5min → Red), survival = f(triage, time_to_hospital, trauma_level)
4. **Deliverable**: Simulator runs with random ambulance policy

### Phase 2: Baselines & RL Setup (Weeks 7-10)
**Establish baselines and RL infrastructure**
1. **Baselines**: Nearest Hospital, Triage-Priority, Trauma Matching, Round Robin (run 100 scenarios each)
2. **Gym Environment**: `MCIResponseEnv` with state (casualties, ambulances, hospitals), action (assign ambulance to casualty+hospital), reward (-1000 per death, +500 per delivery, +200 trauma match, -10/min waiting)
3. **RL Integration**: PPO with Stable-Baselines3, TensorBoard logging
4. **Deliverable**: Working training pipeline

### Phase 3: Training (Weeks 11-16)
**Train agent to beat baselines**
1. Train 500k steps on 200 scenarios (4-8 hrs GPU)
2. Evaluate, debug, tune rewards
3. Final training: 1-2M steps on 500 scenarios (12-20 hrs)
4. **Deliverable**: Agent beats baselines by ≥10%

### Phase 4: Analysis (Weeks 17-22)
**Evaluate and visualize**
1. **Metrics**: Mortality rate, response time, golden hour compliance, hospital load balance
2. **Ablations**: Test without triage priority, without trauma matching, different rewards (4-8 hrs each)
3. **Visualization**: Extend hospital_viz to show scenario playback, ambulance trajectories, decision timeline
4. **Deliverable**: Complete analysis with visualizations

### Phase 5: Documentation (Weeks 23-26)
**Report and presentation**
- Report: Intro, methods, results, discussion
- Presentation: 15-20 min talk with live demo
- **Deliverable**: Thesis/report and clean code repo

---

## Key Technical Details

### Agent Architecture (College Project)
**Centralized Master Agent** (single PPO agent controlling all ambulances)

**State Space**:
```python
{
  'casualties': [[x, y, triage, health_state, time_elapsed], ...],  # Max 80
  'ambulances': [[x, y, status, patient_onboard], ...],             # Max 10
  'hospitals': [[x, y, trauma_level, current_load], ...],          # 8-10
  'incident_location': [x, y],
  'elapsed_time': int
}
```

**Action Space**: For each idle ambulance → select (casualty_id, hospital_id) or "wait"
Action masking prevents invalid actions (already-dispatched, deceased casualties)

**Reward Function**:
- Primary: -1000 per death, +500 per delivery
- Bonus: +200 trauma match (Red → Level I/II), +100 load balancing
- Penalty: -10/min per waiting casualty, -100/min Red waiting, -50 for suboptimal hospital choice

### OpenStreetMap Routing
```python
import osmnx as ox, networkx as nx
G = ox.graph_from_place("Los Angeles County, CA", network_type="drive")
route_time = nx.shortest_path_length(G, origin_node, dest_node, weight='length') / (speed * 1.2)  # Emergency vehicles 1.2x faster
```
Pre-compute distance matrix between hospitals and grid points for speed.

### Patient Deterioration (Markov Model)
- **Red**: 5% per minute → Death (without treatment)
- **Yellow**: 1% per 5 minutes → Red
- **Green**: Stable (no deterioration)
- **Black**: Terminal
- **Treatment effects**: Ambulance pickup reduces deterioration, hospital arrival stops it
- **Survival**: `P(survive) = f(triage_level, time_to_hospital, hospital_trauma_level)`

### Training Setup (PPO)
```python
from stable_baselines3 import PPO
from stable_baselines3.common.env_util import make_vec_env

env = make_vec_env(MCIResponseEnv, n_envs=8)  # 8 parallel environments
model = PPO("MultiInputPolicy", env, learning_rate=3e-4, n_steps=2048,
            batch_size=64, n_epochs=10, gamma=0.99, verbose=1)
model.learn(total_timesteps=1_000_000)
```

**Curriculum Learning (optional)**: Start with 30 casualties, scale to 80
**Scenario Diversity**: Urban/rural locations, varying triage distributions, edge cases

---

## Computational Requirements

### Hardware Configuration
**Target System**: NVIDIA RTX 3050 (8GB VRAM) + Intel CPU
- **GPU**: All RL training (neural networks) must run on CUDA
- **CPU**: Environment simulation, data processing, I/O operations
- **RAM**: 16GB minimum
- **Storage**: 10GB

### CUDA Requirements
**CRITICAL**: All reinforcement learning libraries and training code MUST use NVIDIA CUDA-optimized packages.

**Required Package Versions**:
```bash
# PyTorch with CUDA support (NOT CPU-only version)
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118

# Stable-Baselines3 (automatically uses CUDA if PyTorch has it)
pip install stable-baselines3[extra]

# Training script must specify device='cuda'
model = PPO(..., device='cuda')
```

**Training Time Estimates (RTX 3050)**: 8-12 hours per 1M timesteps, ~40-50 hours total project

---

## Success Criteria

1. **Primary**: ≥10% mortality reduction vs. nearest-hospital baseline
2. **Secondary**: ≥5% faster response, ≥70% golden hour compliance for Red casualties
3. **Technical**: Functional pipeline, evaluation on 100+ test scenarios, visualizations
4. **Documentation**: Report with methodology and results, clean code repo

---

## Future Work (NOT College Project)

### Full System Vision (12+ months)
- **Multi-Agent**: Independent ambulance agents, hospital agents (accept/reject), field trauma center deployment
- **Advanced**: Traffic simulation, crew fatigue, inter-hospital transfers, 10,000+ scenarios
- **MARL**: MAPPO/QMIX for agent coordination
- **Goal**: ≥15% mortality reduction, 1000+ casualties, real-time decisions (<10s)

### Agent Types (Future)
1. **Central Dispatcher**: Deploy field trauma center, request mutual aid, set policies
2. **Ambulance Agents**: Individual decision-making per ambulance
3. **Hospital Agents**: Capacity management, accept/redirect, patient transfers
4. **Field Trauma Center**: Deployment location, setup vs. benefit trade-off

### Technical Challenges (Future)
- **Scalability**: GNNs for variable entities, hierarchical action spaces
- **Credit Assignment**: Difference rewards, Shapley values, counterfactuals
- **Sparse Rewards**: Dense intermediate rewards, reward shaping, HER
- **Safety**: Action masking, constrained RL (CPO/TRPO), protocol validation

---

## Data Requirements

### Available
- ✅ `us_hospital_locations.csv`: location, beds, trauma level, helipad

### Needed
- OpenStreetMap networks (OSMnx)
- Triage protocols (START/SALT)
- Survival probability models (literature)
- Synthetic casualty distributions (literature-based)

---

## Common Pitfalls & Solutions

1. **Agent doesn't learn**: Simplify scenario, add dense rewards, check bugs
2. **Training too slow**: Reduce complexity, use cloud GPU
3. **OSM breaks**: Start with Euclidean distance, add OSM later
4. **Scope creep**: Stick to plan! No field trauma center, traffic, or multi-agent
5. **Environment bugs**: Test with random/heuristic policies before RL

---

## important-instruction-reminders
Do what has been asked; nothing more, nothing less.
NEVER create files unless absolutely necessary.
ALWAYS prefer editing existing files to creating new ones.
NEVER proactively create documentation files (*.md) or README files unless explicitly requested.