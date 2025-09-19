# Implementation Steps for RLRapidResponse

This document provides detailed, actionable steps for implementing each phase of the project.

---

## Phase 1: Environment (Weeks 1-6)
**Goal**: Build a functional simulator without RL that can run with random/heuristic policies.

### Step 1.1: Hospital Data Loader
**File**: `simulator/environment/hospital_loader.py`

**Tasks**:
1. Create function `load_hospitals(region=None)` that:
   - Reads `datasets/us_hospital_locations.csv`
   - Filters by region (e.g., "CA" for California) if specified
   - Returns list of hospital dictionaries with: `id`, `lat`, `lon`, `beds`, `trauma_level`, `helipad`
   - Maps trauma levels: "LEVEL I" → 1, "LEVEL II" → 2, "LEVEL III" → 3, "LEVEL IV" → 4, "NOT AVAILABLE" → 5
2. Add function `get_hospital_by_id(hospitals, hospital_id)`
3. Test: Load California hospitals, verify count and data structure

**Acceptance Criteria**:
- Can load and filter 7,596 hospitals by state
- Trauma levels properly mapped to integers
- Returns clean Python dictionaries

---

### Step 1.2: Scenario Generator
**File**: `simulator/environment/scenario_generator.py`

**Tasks**:
1. Create class `ScenarioGenerator`:
   - `__init__(self, hospitals, region_bounds)`: Takes hospital list and lat/lon bounds
   - `generate_scenario(num_casualties, ambulances_per_hospital, ambulances_per_hospital_variation, field_ambulances, field_ambulance_radius_km, seed)`: Returns scenario dict
2. Implement scenario generation:
   - Random MCI location within region bounds
   - Generate 50-80 casualties around incident location (Gaussian distribution, σ=500m)
   - Assign triage levels: 25% Red, 40% Yellow, 30% Green, 5% Black (numpy.random.choice)
   - **Store ambulance configuration (lazy spawning)**:
     - Do NOT generate actual ambulances in scenario
     - Store config parameters for later spawning by simulation engine
     - Includes seed for reproducibility
3. Implement `spawn_ambulances(incident_location, ambulance_config, hospitals)` method:
   - Called by simulation engine at initialization
   - **Hospital-based**: Each hospital gets `ambulances_per_hospital ± ambulances_per_hospital_variation` ambulances
   - **Field units**: `field_ambulances` placed randomly within `field_ambulance_radius_km` of incident
   - Uses config seed for reproducible spawning
4. Scenario dict structure (lightweight):
   ```python
   {
       'incident_location': [lat, lon],
       'casualties': [
           {'id': 0, 'lat': ..., 'lon': ..., 'triage': 'RED', 'initial_health': 1.0},
           ...
       ],
       'ambulance_config': {
           'ambulances_per_hospital': 2,
           'ambulances_per_hospital_variation': 1,
           'field_ambulances': 5,
           'field_ambulance_radius_km': 10.0,
           'seed': 123  # For reproducibility
       },
       'hospitals': [...],  # From hospital loader
       'timestamp': 0,
       'num_casualties': int
   }
   ```
5. Add method `save_scenario(scenario, filename)` to save as JSON
6. Add method `load_scenario(filename)` to load from JSON
7. Test: Generate 10 scenarios, verify triage distribution and ambulance spawning

**Acceptance Criteria**:
- Generates scenarios with correct casualty counts (50-80)
- Triage distribution matches target (25/40/30/5)
- Casualties clustered around incident location
- Scenario JSON is lightweight (no ambulances stored)
- `spawn_ambulances()` creates hospital-based + field ambulances dynamically
- Same seed produces identical ambulances (reproducibility)
- Can save/load scenarios from JSON efficiently

---

### Step 1.3: Patient Deterioration Model
**File**: `simulator/environment/patient_model.py`

**Tasks**:
1. Create class `PatientModel`:
   - `__init__(self, triage_level)`: Initialize with RED/YELLOW/GREEN/BLACK
   - Attributes: `health` (0.0-1.0), `triage`, `time_since_injury`, `is_alive`, `treatment_status` (WAITING/ENROUTE/DELIVERED)
2. Implement `update(delta_time_minutes)`:
   - RED: Decrease health by 5% per minute if WAITING, 2% if ENROUTE (ambulance slows deterioration)
   - YELLOW: 1% per 5 minutes → deteriorate to RED if health < 0.5
   - GREEN: No deterioration
   - BLACK: Already deceased
   - If health ≤ 0.0, set `is_alive = False`
3. Implement `apply_treatment(treatment_type)`:
   - 'PICKUP': Reduce deterioration rate (ambulance care)
   - 'HOSPITAL': Stop deterioration (set treatment_status = DELIVERED)
4. Implement `get_survival_probability(time_to_hospital, hospital_trauma_level)`:
   - Base survival by triage: RED=0.7, YELLOW=0.9, GREEN=0.98
   - Penalty: -0.1 if time > 60 min (golden hour), -0.05 per 30 min after
   - Bonus: +0.1 if RED/YELLOW → Level I/II hospital
   - Return clamped probability [0.0, 1.0]
5. Test: Simulate 60-minute wait for RED patient, verify health decrease and death

**Acceptance Criteria**:
- RED patients die within ~20 minutes without pickup
- YELLOW patients deteriorate to RED after ~50 minutes
- Ambulance pickup slows deterioration
- Hospital delivery stops deterioration

---

### Step 1.4: Routing Utilities (Euclidean Distance First)
**File**: `simulator/environment/routing.py`

**Tasks**:
1. Create function `euclidean_distance(lat1, lon1, lat2, lon2)`:
   - Use Haversine formula for lat/lon → kilometers
   - Return distance in km
2. Create function `euclidean_travel_time(lat1, lon1, lat2, lon2, speed_kmh=80)`:
   - Calculate distance, return travel time in minutes
   - Emergency vehicles: 80 km/h (1.2x normal speed)
3. Create function `precompute_distance_matrix(locations)`:
   - Takes list of (lat, lon) tuples
   - Returns NxN numpy array of distances
4. Test: Calculate LA downtown → UCLA Medical Center (~20km, ~15 min)

**Acceptance Criteria**:
- Haversine formula correct (test known distances)
- Travel time realistic for emergency vehicles
- Distance matrix computes correctly

**Note**: OSMnx routing will be added later (Step 1.5) if time permits.

---

### Step 1.5: Core Simulation Engine (No RL)
**File**: `simulator/simulation_engine.py`

**Tasks**:
1. Create class `SimulationEngine`:
   - `__init__(self, scenario, policy)`: Takes scenario dict and policy function
   - Attributes: `current_time`, `casualties`, `ambulances`, `hospitals`, `event_log`, `metrics`
   - **Spawn ambulances**: Call `ScenarioGenerator.spawn_ambulances()` during initialization using `scenario['ambulance_config']`
2. Implement main simulation loop:
   ```python
   def run(self, max_time_minutes=180):
       while self.current_time < max_time_minutes and not self.is_done():
           self.step()
           self.current_time += 1  # 1-minute timesteps
   ```
3. Implement `step()`:
   - Update all patient health (call `patient.update(1)`)
   - Check for deaths, log events
   - For each IDLE ambulance, call `policy(state)` to get action
   - Execute actions: dispatch ambulance to casualty, transport to hospital
   - Update ambulance positions (move toward target based on travel time)
4. Implement `is_done()`:
   - Return True if all casualties are delivered or deceased
5. Implement `get_metrics()`:
   - Return dict: `deaths`, `transported`, `avg_response_time`, `casualties_waiting`
6. Implement event bus pattern:
   ```python
   def register_listener(self, callback):
       self.event_listeners.append(callback)

   def emit_event(self, event_type, data):
       for listener in self.event_listeners:
           listener(event_type, data)
   ```
7. Test with random policy: randomly assign idle ambulances to waiting casualties

**Acceptance Criteria**:
- Simulation runs for 180 minutes or until all casualties handled
- Patients deteriorate correctly over time
- Ambulances move toward targets
- Event log records all actions
- Metrics calculated correctly

---

### Step 1.6: Simple Random Policy for Testing
**File**: `simulator/agents/baselines.py`

**Tasks**:
1. Create function `random_policy(state)`:
   - Takes state dict (casualties, ambulances, hospitals)
   - For each idle ambulance: randomly pick a waiting casualty and nearest hospital
   - Return action dict: `{ambulance_id: (casualty_id, hospital_id)}`
2. Create function `nearest_hospital_policy(state)`:
   - For each idle ambulance: pick closest waiting casualty
   - Send to nearest hospital
3. Test both policies with simulator

**Acceptance Criteria**:
- Random policy produces valid actions
- Nearest policy performs better than random
- Can run 100 scenarios and collect metrics

---

### Step 1.7: CLI Interface for Testing
**File**: `simulator/run_simulation.py`

**Tasks**:
1. Create CLI script with argparse:
   ```bash
   python simulator/run_simulation.py \
       --region CA \
       --casualties 60 \
       --ambulances 8 \
       --policy random \
       --output results.json
   ```
2. Load hospitals, generate scenario, run simulation, save results
3. Test: Run 10 scenarios, verify results saved

**Acceptance Criteria**:
- Can run simulations from command line
- Results saved to JSON
- Easy to test different policies

---

## Phase 2: Baselines & RL Setup (Weeks 7-10)
**Goal**: Implement baseline policies and create Gymnasium environment for RL.

### Step 2.1: Implement Baseline Policies
**File**: `simulator/agents/baselines.py` (extend)

**Tasks**:
1. Implement `triage_priority_policy(state)`:
   - Prioritize RED > YELLOW > GREEN
   - Among same triage, choose closest to ambulance
   - Send to nearest hospital
2. Implement `trauma_matching_policy(state)`:
   - RED → Level I/II hospitals
   - YELLOW → Level II/III hospitals
   - GREEN → Any hospital
   - If no match available, use nearest
3. Implement `load_balancing_policy(state)`:
   - Track hospital current load (casualties delivered)
   - Send to least-loaded hospital within trauma match
4. Test all policies: Run 100 scenarios each, compare metrics

**Acceptance Criteria**:
- Triage-priority outperforms random
- Trauma-matching improves RED survival
- Load-balancing reduces hospital congestion

---

### Step 2.2: Create Gymnasium Environment
**File**: `simulator/environment/mci_env.py`

**Tasks**:
1. Create class `MCIResponseEnv(gymnasium.Env)`:
   - Define `observation_space`: Dict with casualties, ambulances, hospitals
   - Define `action_space`: MultiDiscrete (for each ambulance: casualty_id + hospital_id)
2. Implement `reset(seed, options)`:
   - Generate new scenario
   - Return initial observation
3. Implement `step(action)`:
   - Parse action, dispatch ambulances
   - Run simulation for 1 timestep
   - Calculate reward
   - Return (observation, reward, terminated, truncated, info)
4. Implement reward function:
   ```python
   reward = 0
   reward += -1000 * deaths_this_step
   reward += 500 * deliveries_this_step
   reward += 200 * trauma_matches_this_step
   reward += -10 * casualties_waiting
   reward += -100 * red_casualties_waiting
   ```
5. Implement action masking:
   - Mask out deceased casualties, already-dispatched casualties
   - Return valid actions in `info['action_mask']`
6. Test: Create env, run random actions, verify observations/rewards

**Acceptance Criteria**:
- Environment follows Gym API
- Observations have correct shape
- Rewards incentivize correct behavior
- Action masking prevents invalid actions

---

### Step 2.3: Integrate Stable-Baselines3
**File**: `simulator/train.py`

**Tasks**:
1. Create training script:
   ```python
   from stable_baselines3 import PPO
   from stable_baselines3.common.env_util import make_vec_env
   from simulator.environment.mci_env import MCIResponseEnv

   env = make_vec_env(MCIResponseEnv, n_envs=4)
   model = PPO("MultiInputPolicy", env, verbose=1, device='cuda')
   model.learn(total_timesteps=100_000)
   model.save("models/ppo_mci")
   ```
2. Add TensorBoard logging
3. Test: Train for 100k steps, verify learning curve

**Acceptance Criteria**:
- Training runs on GPU (CUDA)
- TensorBoard logs rewards
- Model saves successfully

---

### Step 2.4: Evaluation Script
**File**: `simulator/evaluate.py`

**Tasks**:
1. Create evaluation script:
   ```bash
   python simulator/evaluate.py \
       --model models/ppo_mci.zip \
       --num-scenarios 100 \
       --output evaluation.csv
   ```
2. Compare against all baselines
3. Generate summary statistics: mean deaths, response time, survival rate
4. Test: Evaluate random policy vs. nearest policy

**Acceptance Criteria**:
- Can load trained model
- Runs 100 test scenarios
- Outputs comparison CSV

---

## Phase 3: Training (Weeks 11-16)
**Goal**: Train PPO agent to beat all baselines.

### Step 3.1: Initial Training Run
**Tasks**:
1. Train PPO for 500k steps on 200 diverse scenarios
2. Monitor TensorBoard: reward curve, episode length
3. Evaluate every 50k steps against baselines
4. Expected time: 4-8 hours on RTX 3050

**Acceptance Criteria**:
- Training completes without errors
- Reward increases over time
- Agent performs better than random

---

### Step 3.2: Debug and Tune
**Tasks**:
1. If agent doesn't learn:
   - Simplify scenario (reduce casualties to 30-40)
   - Check reward function (ensure deaths have high penalty)
   - Verify action masking works
   - Check for bugs in environment step logic
2. Tune hyperparameters:
   - Learning rate: try 1e-4, 3e-4, 5e-4
   - Batch size: try 32, 64, 128
   - Entropy coefficient: try 0.01, 0.001
3. Try curriculum learning:
   - Start with 30 casualties, increase to 60, then 80

**Acceptance Criteria**:
- Agent learns to reduce deaths
- Beats nearest-hospital baseline

---

### Step 3.3: Final Training Run
**Tasks**:
1. Train PPO for 1-2M steps on 500 diverse scenarios
2. Use best hyperparameters from tuning
3. Save checkpoints every 100k steps
4. Expected time: 12-20 hours on RTX 3050

**Acceptance Criteria**:
- Agent beats all baselines by ≥10% mortality reduction
- Stable performance across 100 test scenarios

---

## Phase 4: Analysis (Weeks 17-22)
**Goal**: Evaluate trained agent and create visualizations.

### Step 4.1: Comprehensive Evaluation
**File**: `simulator/analysis/evaluate_all.py`

**Tasks**:
1. Run 100 test scenarios for:
   - Random policy
   - Nearest hospital
   - Triage priority
   - Trauma matching
   - Load balancing
   - Trained PPO agent
2. Compute metrics for each:
   - Mortality rate (deaths / total casualties)
   - Average response time (time from injury to pickup)
   - Golden hour compliance (% RED picked up within 60 min)
   - Hospital load balance (std dev of deliveries per hospital)
3. Generate comparison table and plots

**Acceptance Criteria**:
- PPO agent beats all baselines
- Statistical significance test (t-test)
- Results saved to CSV

---

### Step 4.2: Ablation Studies
**File**: `simulator/analysis/ablation.py`

**Tasks**:
1. Train variants:
   - PPO without triage priority reward
   - PPO without trauma matching bonus
   - PPO without load balancing
   - PPO with different reward weights
2. Compare to full PPO agent
3. Determine which components are most important

**Acceptance Criteria**:
- Identify critical reward components
- Understand what the agent learned

---

### Step 4.3: Visualization - Scenario Playback
**File**: `simulator/visualization/playback.py`

**Tasks**:
1. Create function `visualize_scenario(scenario, actions, output_file)`:
   - Use matplotlib to create animation
   - Show map with hospitals (blue), casualties (red/yellow/green), ambulances (moving)
   - Timeline showing actions taken
   - Metric panel showing deaths, transports over time
2. Generate videos for:
   - Best PPO scenario
   - Worst PPO scenario
   - Baseline comparison
3. Test: Create 5-minute playback video

**Acceptance Criteria**:
- Animation shows ambulance movement
- Clear visualization of decisions
- Export to MP4/GIF

---

### Step 4.4: Web Visualization (Optional)
**Files**: `backend/app.py`, `frontend/src/`

**Tasks**:
1. Implement Flask backend:
   - REST API endpoints (see CLAUDE.md)
   - WebSocket integration with SimulationEngine
2. Implement React frontend:
   - Leaflet map with live updates
   - Simulation controls (start/stop/pause/speed)
   - Metrics dashboard
3. Test: Run live simulation in browser

**Acceptance Criteria**:
- Real-time visualization works
- Can control simulation from UI
- Metrics update every timestep

---

## Phase 5: Documentation (Weeks 23-26)
**Goal**: Write report and prepare presentation.

### Step 5.1: Code Cleanup
**Tasks**:
1. Add docstrings to all functions/classes
2. Add type hints
3. Create requirements.txt or ensure pyproject.toml is complete
4. Write README.md with:
   - Project overview
   - Installation instructions
   - Usage examples
   - Results summary
5. Add unit tests (pytest) for critical components

**Acceptance Criteria**:
- Code is well-documented
- Easy for others to run
- Tests pass

---

### Step 5.2: Write Report
**Sections**:
1. **Introduction**: Problem statement, motivation, goals
2. **Related Work**: Existing dispatch systems, RL applications in healthcare
3. **Methods**:
   - System architecture
   - Environment design (state/action/reward)
   - Patient deterioration model
   - PPO algorithm
   - Baseline policies
4. **Results**:
   - Training curves
   - Comparison table
   - Ablation study results
   - Example scenarios
5. **Discussion**:
   - What worked well
   - Limitations (no traffic, simplified model)
   - Future work
6. **Conclusion**: Summary of achievements

**Acceptance Criteria**:
- 20-30 page report
- Clear figures and tables
- References to literature

---

### Step 5.3: Prepare Presentation
**Tasks**:
1. Create 15-20 slide deck:
   - Problem statement (2 slides)
   - Approach (3-4 slides)
   - Results (4-5 slides)
   - Live demo (if possible)
   - Conclusion and future work (2 slides)
2. Practice presentation (15-20 minutes)
3. Prepare to answer questions about:
   - Why PPO instead of other algorithms?
   - How does action masking work?
   - What if agent fails in real emergency?

**Acceptance Criteria**:
- Clear, engaging presentation
- Demo works smoothly
- Confident delivery

---

## Quick Reference: File Structure

```
RLRapidResponse/
├── simulator/
│   ├── environment/
│   │   ├── hospital_loader.py       # Step 1.1
│   │   ├── scenario_generator.py    # Step 1.2
│   │   ├── patient_model.py         # Step 1.3
│   │   ├── routing.py               # Step 1.4
│   │   └── mci_env.py               # Step 2.2
│   ├── agents/
│   │   └── baselines.py             # Step 1.6, 2.1
│   ├── simulation_engine.py         # Step 1.5
│   ├── run_simulation.py            # Step 1.7
│   ├── train.py                     # Step 2.3
│   └── evaluate.py                  # Step 2.4
├── datasets/
│   └── us_hospital_locations.csv
├── models/                          # Trained models saved here
├── results/                         # Evaluation results
├── CLAUDE.md
├── STEPS.md                         # This file
└── pyproject.toml
```

---

## Testing Strategy

After each step:
1. **Unit test**: Test the specific function/class in isolation
2. **Integration test**: Test with rest of system
3. **End-to-end test**: Run full simulation and verify output

Example for Step 1.3 (Patient Model):
```python
# Unit test
patient = PatientModel('RED')
for i in range(20):
    patient.update(1)
assert not patient.is_alive  # Should die after ~20 min

# Integration test
scenario = generate_scenario(60, 8)
engine = SimulationEngine(scenario, random_policy)
engine.run()
assert engine.metrics['deaths'] > 0  # Some should die

# End-to-end test
python simulator/run_simulation.py --casualties 60 --policy random
# Check results.json has valid structure
```

---

## Common Issues and Solutions

### Issue: Training too slow
- Reduce num_casualties to 40-50
- Use fewer parallel environments (n_envs=4 instead of 8)
- Simplify state space (remove unnecessary features)

### Issue: Agent doesn't learn
- Check reward function (deaths should have large penalty)
- Verify action masking (invalid actions should be masked)
- Simplify environment (fewer ambulances/casualties)
- Check for bugs in step() logic

### Issue: Environment hangs
- Add max_steps limit to simulation
- Check for infinite loops in routing
- Add timeout to step()

### Issue: CUDA out of memory
- Reduce batch_size
- Reduce n_envs
- Use smaller network (net_arch=[64, 64] instead of [256, 256])

---

## Checkpoint Verification

Use this checklist to verify each phase is complete before moving to the next:

### Phase 1 Complete?
- [ ] Can load hospital data
- [ ] Can generate random scenarios
- [ ] Patients deteriorate correctly
- [ ] Simulation runs for 180 minutes
- [ ] Multiple policies implemented
- [ ] CLI works

### Phase 2 Complete?
- [ ] All 4 baseline policies work
- [ ] Gym environment follows API
- [ ] Action masking works
- [ ] Reward function implemented
- [ ] Training runs on GPU
- [ ] Evaluation script works

### Phase 3 Complete?
- [ ] Agent beats random policy
- [ ] Agent beats all baselines by ≥10%
- [ ] Model saved and can be loaded
- [ ] Training curves look good

### Phase 4 Complete?
- [ ] 100 test scenarios evaluated
- [ ] Ablation studies done
- [ ] Visualizations created
- [ ] Results documented

### Phase 5 Complete?
- [ ] Code documented
- [ ] Report written
- [ ] Presentation prepared
- [ ] Demo works