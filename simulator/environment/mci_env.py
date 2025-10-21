"""
Gymnasium Environment for Mass Casualty Incident Response - Step 2.2
"""

import numpy as np
import gymnasium as gym
from gymnasium import spaces
from typing import Dict, Tuple, Optional, Any
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from simulator.environment.scenario_generator import ScenarioGenerator
from simulator.environment.hospital_loader import load_hospitals
from simulator.simulation_engine import SimulationEngine


class MCIResponseEnv(gym.Env):
    metadata = {'render_modes': ['human']}

    def __init__(
        self,
        region='CA',
        max_casualties=100,
        max_ambulances=50,
        max_hospitals=200,
        max_time_minutes=180,
        num_casualties_range=(50, 80),
        ambulances_per_hospital=2,
        ambulances_per_hospital_variation=1,
        field_ambulances=5,
        field_ambulance_radius_km=10.0
    ):
        super().__init__()

        self.region = region
        self.max_casualties = max_casualties
        self.max_ambulances = max_ambulances
        self.max_hospitals = max_hospitals
        self.max_time_minutes = max_time_minutes
        self.num_casualties_range = num_casualties_range

        self.ambulance_config = {
            'ambulances_per_hospital': ambulances_per_hospital,
            'ambulances_per_hospital_variation': ambulances_per_hospital_variation,
            'field_ambulances': field_ambulances,
            'field_ambulance_radius_km': field_ambulance_radius_km,
            'seed': None
        }

        self.hospitals = load_hospitals(region=region)
        if len(self.hospitals) > max_hospitals:
            self.hospitals = self.hospitals[:max_hospitals]

        self.region_bounds = self._get_region_bounds()

        self.scenario_generator = ScenarioGenerator(self.hospitals, self.region_bounds)
        self.simulation_engine: Optional[SimulationEngine] = None
        self.scenario: Optional[Dict] = None
        self._pending_actions: Dict = {}
        self._previous_metrics: Dict = {}

        self._define_spaces()

    def _get_region_bounds(self) -> Tuple[float, float, float, float]:
        if not self.hospitals:
            return (33.0, 34.5, -119.0, -117.0)

        lats = [h['lat'] for h in self.hospitals]
        lons = [h['lon'] for h in self.hospitals]
        return (min(lats), max(lats), min(lons), max(lons))

    def _define_spaces(self):
        self.observation_space = spaces.Dict({
            'casualties': spaces.Box(
                low=0.0, high=1.0,
                shape=(self.max_casualties, 6),
                dtype=np.float32
            ),
            'ambulances': spaces.Box(
                low=0.0, high=1.0,
                shape=(self.max_ambulances, 7),
                dtype=np.float32
            ),
            'hospitals': spaces.Box(
                low=0.0, high=1.0,
                shape=(self.max_hospitals, 5),
                dtype=np.float32
            ),
            'incident_location': spaces.Box(
                low=0.0, high=1.0,
                shape=(2,),
                dtype=np.float32
            ),
            'current_time': spaces.Box(
                low=0.0, high=1.0,
                shape=(1,),
                dtype=np.float32
            )
        })

        # Simplified discrete action space: for each idle ambulance, select (casualty_id, hospital_id) or WAIT
        # We'll use a MultiDiscrete space representing actions for multiple ambulances
        # Each ambulance gets: casualty_id (0=WAIT, 1-N=casualties) and hospital_id (0-M hospitals)
        self.action_space = spaces.MultiDiscrete([
            self.max_casualties + 1,  # casualty selection (0 = WAIT)
            self.max_hospitals        # hospital selection
        ] * self.max_ambulances)

    def reset(self, seed: Optional[int] = None, options: Optional[Dict[str, Any]] = None) -> Tuple[Dict, Dict]:
        super().reset(seed=seed)

        if options and 'scenario_file' in options:
            import json
            with open(options['scenario_file'], 'r') as f:
                self.scenario = json.load(f)
        else:
            num_casualties = self.np_random.integers(
                self.num_casualties_range[0],
                self.num_casualties_range[1] + 1
            )

            self.ambulance_config['seed'] = int(seed) if seed is not None else int(self.np_random.integers(0, 1_000_000))

            self.scenario = self.scenario_generator.generate_scenario(
                num_casualties=num_casualties,
                ambulances_per_hospital=self.ambulance_config['ambulances_per_hospital'],
                ambulances_per_hospital_variation=self.ambulance_config['ambulances_per_hospital_variation'],
                field_ambulances=self.ambulance_config['field_ambulances'],
                field_ambulance_radius_km=self.ambulance_config['field_ambulance_radius_km'],
                seed=self.ambulance_config['seed']
            )

        # Create internal policy that applies RL actions
        def rl_policy(state: Dict) -> Dict:
            return self._pending_actions

        assert self.scenario is not None
        self.simulation_engine = SimulationEngine(self.scenario, rl_policy)
        self._previous_metrics = self.simulation_engine.get_metrics().copy()

        observation = self._get_observation()
        info = self._get_info()

        return observation, info

    def step(self, action: np.ndarray) -> Tuple[Dict, float, bool, bool, Dict]:
        assert self.simulation_engine is not None, "Must call reset() before step()"

        # Parse RL action into ambulance actions
        parsed_actions = self._parse_action(action)
        self._pending_actions = parsed_actions

        # Execute one simulation step
        self.simulation_engine.step()

        # Calculate reward based on state change
        current_metrics = self.simulation_engine.get_metrics()
        reward = self._calculate_reward(self._previous_metrics, current_metrics)
        self._previous_metrics = current_metrics.copy()

        # Get new observation
        observation = self._get_observation()
        info = self._get_info()

        # Check termination conditions
        terminated = self.simulation_engine.is_done()
        truncated = self.simulation_engine.current_time >= self.max_time_minutes

        return observation, reward, terminated, truncated, info

    def _parse_action(self, action: np.ndarray) -> Dict:
        assert self.simulation_engine is not None

        actions = {}
        action_pairs = action.reshape(-1, 2)

        idle_ambulances = [
            amb for amb in self.simulation_engine.ambulances
            if amb['status'] == 'IDLE'
        ]

        for idx, amb in enumerate(idle_ambulances):
            if idx >= len(action_pairs):
                break

            casualty_idx, hospital_idx = action_pairs[idx]

            # 0 means WAIT
            if casualty_idx == 0:
                continue

            casualty_id = casualty_idx - 1

            # Validate action
            if casualty_id >= len(self.simulation_engine.casualties):
                continue
            if hospital_idx >= len(self.simulation_engine.hospitals):
                continue

            casualty = self.simulation_engine.casualties[casualty_id]

            # Check if action is valid
            if not casualty['patient'].is_alive:
                continue
            if casualty['status'] != 'WAITING':
                continue

            hospital_id = self.simulation_engine.hospitals[hospital_idx]['id']

            actions[amb['id']] = {
                'action_type': 'DISPATCH_TO_CASUALTY',
                'casualty_id': casualty_id,
                'hospital_id': hospital_id
            }

        return actions

    def _calculate_reward(self, prev_metrics: Dict, curr_metrics: Dict) -> float:
        assert self.simulation_engine is not None

        reward = 0.0

        # Primary objectives
        deaths_delta = curr_metrics['deaths'] - prev_metrics['deaths']
        deliveries_delta = curr_metrics['transported'] - prev_metrics['transported']

        reward += -1000 * deaths_delta
        reward += 500 * deliveries_delta

        # Secondary objectives
        trauma_matches = self._count_trauma_matches()
        reward += 200 * trauma_matches

        golden_hour_compliance = self._count_golden_hour_compliance()
        reward += 100 * golden_hour_compliance

        # Tertiary objectives
        red_waiting = sum(
            1 for c in self.simulation_engine.casualties
            if c['patient'].is_alive and c['status'] == 'WAITING' and c['triage'] == 'RED'
        )
        reward += -100 * red_waiting

        casualties_waiting = sum(
            1 for c in self.simulation_engine.casualties
            if c['patient'].is_alive and c['status'] == 'WAITING'
        )
        reward += -10 * casualties_waiting

        idle_ambulances = sum(
            1 for a in self.simulation_engine.ambulances
            if a['status'] == 'IDLE' and casualties_waiting > 0
        )
        reward += -5 * idle_ambulances

        return reward

    def _count_trauma_matches(self) -> int:
        assert self.simulation_engine is not None

        count = 0
        for event in self.simulation_engine.event_log[-10:]:
            if event['type'] == 'delivery':
                casualty_id = event['casualty_id']
                hospital_id = event['hospital_id']

                casualty = self.simulation_engine.casualties[casualty_id]
                hospital = next((h for h in self.simulation_engine.hospitals if h['id'] == hospital_id), None)

                if hospital and casualty['triage'] == 'RED' and hospital['trauma_level'] in [1, 2]:
                    count += 1

        return count

    def _count_golden_hour_compliance(self) -> int:
        assert self.simulation_engine is not None

        count = 0
        for event in self.simulation_engine.event_log[-10:]:
            if event['type'] == 'pickup':
                casualty_id = event['casualty_id']
                casualty = self.simulation_engine.casualties[casualty_id]

                if casualty['triage'] == 'RED' and casualty['patient'].time_since_injury <= 60:
                    count += 1

        return count

    def _get_observation(self) -> Dict:
        assert self.simulation_engine is not None
        assert self.scenario is not None

        casualties_obs = np.zeros((self.max_casualties, 6), dtype=np.float32)
        ambulances_obs = np.zeros((self.max_ambulances, 7), dtype=np.float32)
        hospitals_obs = np.zeros((self.max_hospitals, 5), dtype=np.float32)

        # Normalize lat/lon
        lat_min, lat_max, lon_min, lon_max = self.region_bounds

        def norm_lat(lat):
            return (lat - lat_min) / (lat_max - lat_min) if lat_max > lat_min else 0.5

        def norm_lon(lon):
            return (lon - lon_min) / (lon_max - lon_min) if lon_max > lon_min else 0.5

        # Encode casualties
        for i, cas in enumerate(self.simulation_engine.casualties[:self.max_casualties]):
            casualties_obs[i] = [
                norm_lat(cas['lat']),
                norm_lon(cas['lon']),
                self._encode_triage(cas['triage']),
                cas['patient'].health,
                1.0 if cas['patient'].is_alive else 0.0,
                self._encode_casualty_status(cas['status'])
            ]

        # Encode ambulances
        for i, amb in enumerate(self.simulation_engine.ambulances[:self.max_ambulances]):
            base_hospital_id = amb.get('base_hospital_id', -1)
            base_hospital_idx = -1

            if base_hospital_id != -1:
                for idx, h in enumerate(self.simulation_engine.hospitals):
                    if h['id'] == base_hospital_id:
                        base_hospital_idx = idx
                        break

            ambulances_obs[i] = [
                norm_lat(amb['lat']),
                norm_lon(amb['lon']),
                self._encode_ambulance_status(amb['status']),
                self._encode_ambulance_type(amb['type']),
                1.0 if amb['patient_onboard'] is not None else 0.0,
                (base_hospital_idx + 1) / self.max_hospitals if base_hospital_idx >= 0 else 0.0,
                min(amb['time_to_target'] / 180.0, 1.0) if amb['time_to_target'] else 0.0
            ]

        # Encode hospitals
        for i, hosp in enumerate(self.hospitals[:self.max_hospitals]):
            hospitals_obs[i] = [
                norm_lat(hosp['lat']),
                norm_lon(hosp['lon']),
                hosp['trauma_level'] / 5.0,
                min(hosp['beds'] / 500.0, 1.0),
                1.0 if hosp.get('helipad', False) else 0.0
            ]

        incident_lat, incident_lon = self.scenario['incident_location']

        return {
            'casualties': casualties_obs,
            'ambulances': ambulances_obs,
            'hospitals': hospitals_obs,
            'incident_location': np.array([norm_lat(incident_lat), norm_lon(incident_lon)], dtype=np.float32),
            'current_time': np.array([self.simulation_engine.current_time / self.max_time_minutes], dtype=np.float32)
        }

    def _encode_triage(self, triage: str) -> float:
        mapping = {'RED': 0.0, 'YELLOW': 0.33, 'GREEN': 0.67, 'BLACK': 1.0}
        return mapping.get(triage, 0.5)

    def _encode_casualty_status(self, status: str) -> float:
        mapping = {'WAITING': 0.0, 'ASSIGNED': 0.25, 'ENROUTE': 0.5, 'DELIVERED': 0.75, 'DECEASED': 1.0}
        return mapping.get(status, 0.0)

    def _encode_ambulance_status(self, status: str) -> float:
        mapping = {
            'IDLE': 0.0,
            'MOVING_TO_CASUALTY': 0.25,
            'MOVING_TO_HOSPITAL': 0.5,
            'MOVING_TO_LOCATION': 0.75,
            'RETURNING_TO_BASE': 1.0
        }
        return mapping.get(status, 0.0)

    def _encode_ambulance_type(self, amb_type: str) -> float:
        return 0.0 if amb_type == 'HOSPITAL_BASED' else 1.0

    def _get_info(self) -> Dict:
        assert self.simulation_engine is not None

        info = {
            'metrics': self.simulation_engine.get_metrics(),
            'current_time': self.simulation_engine.current_time,
            'num_casualties': len(self.simulation_engine.casualties),
            'num_ambulances': len(self.simulation_engine.ambulances),
            'num_hospitals': len(self.simulation_engine.hospitals),
            'action_mask': self._get_action_mask()
        }
        return info

    def _get_action_mask(self) -> Dict:
        """Generate mask for valid actions per ambulance"""
        assert self.simulation_engine is not None

        casualty_masks = []
        hospital_masks = []

        idle_ambulances = [amb for amb in self.simulation_engine.ambulances if amb['status'] == 'IDLE']

        for amb_idx in range(self.max_ambulances):
            if amb_idx < len(idle_ambulances):
                # Valid casualty selections
                casualty_mask = [True]  # WAIT always valid

                for cas_idx, casualty in enumerate(self.simulation_engine.casualties):
                    if cas_idx >= self.max_casualties:
                        break
                    valid = casualty['patient'].is_alive and casualty['status'] == 'WAITING'
                    casualty_mask.append(valid)

                # Pad to max
                while len(casualty_mask) < self.max_casualties + 1:
                    casualty_mask.append(False)

                # All hospitals valid for dispatch
                hospital_mask = [True] * len(self.simulation_engine.hospitals)
                while len(hospital_mask) < self.max_hospitals:
                    hospital_mask.append(False)
            else:
                # No valid actions for non-existent ambulances
                casualty_mask = [False] * (self.max_casualties + 1)
                hospital_mask = [False] * self.max_hospitals

            casualty_masks.append(casualty_mask)
            hospital_masks.append(hospital_mask)

        return {
            'casualty_masks': np.array(casualty_masks, dtype=bool),
            'hospital_masks': np.array(hospital_masks, dtype=bool)
        }

    def render(self):
        if self.simulation_engine is None:
            return

        print(f"\nTime: {self.simulation_engine.current_time} min")
        print(f"Casualties - Alive: {sum(1 for c in self.simulation_engine.casualties if c['patient'].is_alive)}, "
              f"Waiting: {sum(1 for c in self.simulation_engine.casualties if c['status'] == 'WAITING')}, "
              f"Deaths: {self.simulation_engine.metrics['deaths']}")
        print(f"Ambulances - Idle: {sum(1 for a in self.simulation_engine.ambulances if a['status'] == 'IDLE')}, "
              f"Busy: {sum(1 for a in self.simulation_engine.ambulances if a['status'] != 'IDLE')}")


if __name__ == '__main__':
    print("Testing MCIResponseEnv...")
    print("=" * 60)

    env = MCIResponseEnv(region='CA', max_hospitals=20)

    print(f"\nObservation space: {env.observation_space}")
    print(f"Action space: {env.action_space}")

    print("\nRunning 10 random steps...")
    obs, info = env.reset(seed=42)

    print("Initial state:")
    print(f"  Casualties: {info['num_casualties']}")
    print(f"  Ambulances: {info['num_ambulances']}")
    print(f"  Deaths: {info['metrics']['deaths']}")

    for step_num in range(10):
        action = env.action_space.sample()
        obs, reward, terminated, truncated, info = env.step(action)

        print(f"\nStep {step_num + 1}:")
        print(f"  Reward: {reward:.1f}")
        print(f"  Deaths: {info['metrics']['deaths']}")
        print(f"  Transported: {info['metrics']['transported']}")
        print(f"  Time: {info['current_time']} min")

        if terminated or truncated:
            print("Episode ended!")
            break

    print("\n" + "=" * 60)
    print("✓ Environment test completed!")
