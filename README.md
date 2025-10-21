# RLRapidResponse

Mass Casualty Incident (MCI) response optimization using Reinforcement Learning. Train PPO agents to optimize ambulance dispatch during large-scale emergency events to minimize patient deaths.


## Quick Start

### Installation

This project uses [uv](https://docs.astral.sh/uv/) - a fast Python package manager.

```bash
# Install dependencies (creates .venv automatically)
uv sync
```

### Basic Commands

```bash
# Run simulation with baseline policy
uv run python mci_cli.py simulate --scenario-file scenarios/benchmark/tampa_1.json --policy nearest

# Train RL agent
uv run python mci_cli.py train --timesteps 1000000 --output models/ppo_mci

# Evaluate trained model
uv run python mci_cli.py evaluate --model models/ppo_mci.zip --baselines all --num-scenarios 100
```

## CLI Reference

### 1. Simulation (`simulate`)

Run simulations with baseline policies or trained models.

#### Using Pre-generated Scenarios

```bash
# Run benchmark scenario with nearest-hospital policy
uv run python simulator/run_simulation.py --scenario-file scenarios/benchmark/tampa_1.json --policy nearest

# Try different policies
uv run python simulator/run_simulation.py --scenario-file scenarios/benchmark/tampa_2.json --policy triage
uv run python simulator/run_simulation.py --scenario-file scenarios/benchmark/tampa_1.json --policy trauma

# Save results to file
uv run python simulator/run_simulation.py --scenario-file scenarios/benchmark/tampa_1.json \
    --policy load_balancing --output results.json
```

#### Generating Random Scenarios

```bash
# Generate random scenario for California
uv run python simulator/run_simulation.py --region CA --casualties 60 --policy nearest

# Custom ambulance configuration
uv run python simulator/run_simulation.py --region CA --casualties 60 \
    --ambulances-per-hospital 2 --ambulance-variation 1 \
    --field-ambulances 5 --policy triage

# Run multiple scenarios
uv run python simulator/run_simulation.py --region CA --casualties 60 \
    --policy load_balancing --num-scenarios 10 --output batch_results.json
```

#### Available Policies

- `random` - Random dispatch (baseline)
- `nearest` - Nearest hospital (greedy)
- `triage` - Triage priority (RED > YELLOW > GREEN)
- `trauma` - Trauma center matching (critical patients → Level I/II)
- `load_balancing` - Distribute patients evenly across hospitals

### 2. Training (`train`)

Train PPO agents using Stable-Baselines3.

#### Basic Training

```bash
# Quick test training (100k steps)
uv run python simulator/train.py --timesteps 100000 --output models/test_ppo

# Full training run (1M steps)
uv run python simulator/train.py --timesteps 1000000 --output models/ppo_mci

# Multi-environment parallel training
uv run python simulator/train.py --timesteps 1000000 --output models/ppo_mci --n-envs 8
```

#### Advanced Training Options

```bash
# Training with custom hyperparameters
uv run python simulator/train.py --timesteps 1000000 \
    --output models/ppo_custom \
    --learning-rate 0.0001 \
    --batch-size 128 \
    --n-epochs 15 \
    --ent-coef 0.01

# GPU training with checkpointing
uv run python simulator/train.py --timesteps 2000000 \
    --output models/ppo_final \
    --device cuda \
    --n-envs 16 \
    --checkpoint-freq 50000

# Resume training from checkpoint
uv run python simulator/train.py --timesteps 500000 \
    --load models/ppo_mci.zip \
    --output models/ppo_mci_continued
```

#### Training Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--timesteps` | 100000 | Total training timesteps |
| `--output` | models/ppo_mci | Model save path |
| `--n-envs` | 4 | Parallel environments |
| `--learning-rate` | 0.0003 | PPO learning rate |
| `--batch-size` | 64 | Minibatch size |
| `--n-steps` | 2048 | Steps per env per update |
| `--device` | auto | cpu, cuda, or auto |
| `--checkpoint-freq` | 50000 | Checkpoint interval |

#### Monitoring Training

```bash
# View training progress with TensorBoard
tensorboard --logdir logs/tensorboard
```

### 3. Evaluation (`evaluate`)

Evaluate trained models and compare against baselines.

#### Evaluate Trained Model

```bash
# Evaluate PPO model on 100 scenarios
uv run python simulator/evaluate.py --model models/ppo_mci.zip --num-scenarios 100

# Compare against all baselines
uv run python simulator/evaluate.py --model models/ppo_mci.zip --baselines all --num-scenarios 100

# Save detailed results
uv run python simulator/evaluate.py --model models/ppo_mci.zip --baselines all \
    --num-scenarios 100 --output evaluation_results.json
```

#### Evaluate Baseline Policies Only

```bash
# Test all baselines
uv run python simulator/evaluate.py --baselines all --num-scenarios 100

# Test specific baselines
uv run python simulator/evaluate.py --baselines nearest triage trauma --num-scenarios 50
```

#### Evaluation Output

The evaluation produces:
- Mean ± std for deaths, transported, and response times
- Min/max values across episodes
- Improvement percentages (PPO vs baselines)
- JSON output with full episode details

Example output:
```
PPO Improvement vs Baselines
======================================================================
  vs NEAREST: +12.45% mortality reduction
  vs TRIAGE: +8.32% mortality reduction
  vs TRAUMA: +6.78% mortality reduction
```

### 4. Unified CLI

Use `mci_cli.py` as a single entry point:

```bash
# Simulate
python mci_cli.py simulate --scenario-file scenarios/benchmark/tampa_1.json --policy nearest

# Train
python mci_cli.py train --timesteps 1000000 --output models/ppo_mci

# Evaluate
python mci_cli.py evaluate --model models/ppo_mci.zip --baselines all --num-scenarios 100
```


### Implemented Features

**✓ Data & Infrastructure**
- US hospital database (565+ hospitals across multiple states)
- Hospital metadata: location, trauma level, beds, helipad
- Benchmark scenarios for Tampa Bay area
- Lazy ambulance spawning for efficient storage

**✓ Simulation Engine**
- Discrete-event simulator with 1-minute timesteps
- Markov-based patient deterioration (RED: 5%/min, YELLOW: 1%/5min)
- START triage system (RED/YELLOW/GREEN/BLACK)
- Haversine routing with emergency vehicle speeds
- Hospital-based + field unit ambulance management

**✓ Baseline Policies**
- Random dispatch
- Nearest hospital (greedy)
- Triage priority (RED > YELLOW > GREEN)
- Trauma center matching
- Load balancing

**✓ Reinforcement Learning**
- Gymnasium environment (MCIResponseEnv)
- Multi-objective reward function (deaths, deliveries, trauma matching, golden hour)
- Action masking for invalid actions
- Stable-Baselines3 PPO integration
- TensorBoard logging
- Checkpoint system
- Evaluation callbacks

**✓ CLI Tools**
- Simulation runner (`run_simulation.py`)
- Training script (`train.py`)
- Evaluation script (`evaluate.py`)
- Unified CLI (`mci_cli.py`)

### Next Steps

**Phase 3: Training & Optimization**
- Train PPO on 500+ diverse scenarios (1-2M timesteps)
- Hyperparameter tuning (learning rate, batch size, entropy coefficient)
- Curriculum learning experiments
- Ablation studies on reward components

### Known Limitations

- Haversine routing (no real road networks yet)
- No traffic simulation
- Single master agent (not multi-agent)
- No inter-hospital transfers
- No field trauma center deployment

## Project Structure

```
RLRapidResponse/
├── datasets/
│   └── us_hospital_locations.csv       # Hospital database
├── simulator/
│   ├── environment/
│   │   ├── hospital_loader.py          # Load hospital data
│   │   ├── scenario_generator.py       # Generate MCI scenarios
│   │   ├── patient_model.py            # Patient deterioration model
│   │   ├── routing.py                  # Distance/travel time calculations
│   │   └── mci_env.py                  # Gymnasium environment
│   ├── agents/
│   │   └── baselines.py                # Baseline dispatch policies
│   ├── simulation_engine.py            # Core discrete-event simulator
│   ├── run_simulation.py               # Simulation CLI
│   ├── train.py                        # Training CLI
│   └── evaluate.py                     # Evaluation CLI
├── scenarios/benchmark/                 # Pre-generated test scenarios
├── models/                              # Trained model checkpoints
├── logs/                                # Training logs (TensorBoard)
├── mci_cli.py                           # Unified CLI entry point
├── CLAUDE.md                            # Project documentation
├── STEPS.md                             # Implementation steps
└── README.md                            # This file
```

## Technical Details

### Environment Specifications

**Observation Space** (Dict):
- `casualties`: [lat, lon, triage, health, alive, status] × max_casualties
- `ambulances`: [lat, lon, status, type, has_patient, base_hospital, time_to_target] × max_ambulances
- `hospitals`: [lat, lon, trauma_level, beds, helipad] × max_hospitals
- `incident_location`: [lat, lon]
- `current_time`: normalized time [0, 1]

**Action Space** (MultiDiscrete):
- For each ambulance: select casualty (0=WAIT, 1-N=casualties) + hospital destination

**Reward Function**:
- Primary: -1000 per death, +500 per delivery
- Secondary: +200 trauma match, +100 golden hour compliance
- Penalties: -100 RED waiting, -10 casualties waiting, -5 idle ambulances

### Patient Deterioration Model

| Triage | Waiting Rate | Enroute Rate | Notes |
|--------|-------------|--------------|-------|
| RED | -5%/min | -2%/min | Death in ~20 min without care |
| YELLOW | -0.2%/min | -0.1%/min | Deteriorates to RED at health < 0.5 |
| GREEN | 0%/min | 0%/min | Stable |
| BLACK | Dead | Dead | Terminal |

### Training Recommendations

**Quick Test** (30 min - 1 hour):
```bash
uv run python simulator/train.py --timesteps 100000 --n-envs 4 --device auto
```

**Full Training** (8-12 hours on RTX 3050):
```bash
uv run python simulator/train.py --timesteps 1000000 --n-envs 8 --device cuda \
    --checkpoint-freq 50000 --eval-freq 10000
```

**Production Training** (20-30 hours):
```bash
uv run python simulator/train.py --timesteps 2000000 --n-envs 16 --device cuda \
    --learning-rate 0.0003 --batch-size 128
```

## License

Academic/Educational Project

---

