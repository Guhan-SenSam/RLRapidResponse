"""
Simulation Manager - Multi-Simulation Controller

Manages multiple concurrent simulation instances with independent state tracking.
Provides thread-safe operations for creating, running, and controlling simulations.
"""

import threading
import uuid
import time
import logging
from datetime import datetime
from typing import Dict, Optional, Callable
from enum import Enum
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from simulator.simulation_engine import SimulationEngine
from simulator.environment.scenario_generator import ScenarioGenerator
from simulator.environment.hospital_loader import load_hospitals
from simulator.agents.baselines import (
    random_policy,
    nearest_hospital_policy,
    triage_priority_policy,
    trauma_matching_policy
)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SimulationStatus(Enum):
    """Enumeration of possible simulation states."""
    CREATED = "created"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    COMPLETED = "completed"
    ERROR = "error"


class SimulationInstance:
    """
    Represents a single simulation instance with its configuration and state.

    Attributes:
        id: Unique simulation identifier
        scenario_config: Configuration for scenario generation
        agent_type: Type of agent/policy to use
        status: Current simulation status
        engine: SimulationEngine instance (None until started)
        thread: Background thread running the simulation
        speed: Playback speed multiplier (1.0 = real-time)
        created_at: Timestamp when simulation was created
        started_at: Timestamp when simulation started
        ended_at: Timestamp when simulation ended
        current_metrics: Cached metrics from last update
        error_message: Error message if status is ERROR
    """

    def __init__(self, simulation_id: str, scenario_config: dict, agent_type: str):
        self.id = simulation_id
        self.scenario_config = scenario_config
        self.agent_type = agent_type
        self.status = SimulationStatus.CREATED
        self.engine: Optional[SimulationEngine] = None
        self.thread: Optional[threading.Thread] = None
        self.speed = 1.0
        self.created_at = datetime.utcnow()
        self.started_at: Optional[datetime] = None
        self.ended_at: Optional[datetime] = None
        self.current_metrics: Dict = {}
        self.error_message: Optional[str] = None
        self.scenario: Optional[Dict] = None  # Store loaded scenario

    def to_dict(self) -> Dict:
        """Convert instance to dictionary for API responses."""
        return {
            'id': self.id,
            'status': self.status.value,
            'agent_type': self.agent_type,
            'created_at': self.created_at.isoformat(),
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'ended_at': self.ended_at.isoformat() if self.ended_at else None,
            'current_time': self.engine.current_time if self.engine else 0,
            'metrics': self.current_metrics,
            'speed': self.speed,
            'error_message': self.error_message
        }


class SimulationManager:
    """
    Manages multiple simulation instances with thread-safe operations.

    Handles creation, execution, and control of concurrent simulations.
    Integrates with WebSocket for real-time event broadcasting.
    """

    def __init__(self, socketio):
        """
        Initialize simulation manager.

        Args:
            socketio: Flask-SocketIO instance for broadcasting events
        """
        self.socketio = socketio
        self.simulations: Dict[str, SimulationInstance] = {}
        self.lock = threading.Lock()

        # Policy registry
        self.policies = {
            'random': random_policy,
            'nearest_hospital': nearest_hospital_policy,
            'triage_priority': triage_priority_policy,
            'trauma_matching': trauma_matching_policy,
        }

        # Cache hospitals for scenario generation
        self._hospitals_cache: Optional[list] = None

        logger.info("SimulationManager initialized")

    def create_simulation(self, scenario_config: dict, agent_type: str) -> str:
        """
        Create a new simulation instance.

        Args:
            scenario_config: Configuration for scenario generation
                {
                    'type': 'random' | 'file',
                    'file': 'path/to/scenario.json' (if type='file'),
                    'region': 'CA' (if type='random'),
                    'num_casualties': 60 (if type='random'),
                    'ambulances_per_hospital': 2,
                    'field_ambulances': 5,
                    'seed': 123 (optional)
                }
            agent_type: Policy type ('random', 'nearest_hospital', etc.)

        Returns:
            Simulation ID (UUID)
        """
        simulation_id = str(uuid.uuid4())
        instance = SimulationInstance(simulation_id, scenario_config, agent_type)

        with self.lock:
            self.simulations[simulation_id] = instance

        logger.info(f"Created simulation {simulation_id} with agent {agent_type}")
        return simulation_id

    def get_simulation(self, simulation_id: str) -> Optional[SimulationInstance]:
        """
        Get simulation instance by ID.

        Args:
            simulation_id: Simulation UUID

        Returns:
            SimulationInstance or None if not found
        """
        return self.simulations.get(simulation_id)

    def list_simulations(self) -> list:
        """
        List all simulations with metadata.

        Returns:
            List of simulation dictionaries
        """
        with self.lock:
            return [sim.to_dict() for sim in self.simulations.values()]

    def start_simulation(self, simulation_id: str) -> dict:
        """
        Start a simulation in background thread.

        Args:
            simulation_id: Simulation UUID

        Returns:
            Status dictionary
        """
        instance = self.get_simulation(simulation_id)
        if not instance:
            return {'error': 'Simulation not found', 'success': False}

        if instance.status in [SimulationStatus.RUNNING, SimulationStatus.COMPLETED]:
            return {'error': f'Simulation is {instance.status.value}', 'success': False}

        try:
            # Load scenario
            scenario = self._load_scenario(instance.scenario_config)
            instance.scenario = scenario

            # Get policy
            policy = self._get_policy(instance.agent_type)

            # Create simulation engine
            instance.engine = SimulationEngine(scenario, policy)

            # Register event listener for WebSocket broadcasting
            instance.engine.register_listener(
                lambda event_type, data: self._on_simulation_event(simulation_id, event_type, data)
            )

            # Update status
            instance.status = SimulationStatus.RUNNING
            instance.started_at = datetime.utcnow()

            # Start simulation thread
            instance.thread = threading.Thread(
                target=self._run_simulation_loop,
                args=(simulation_id,),
                daemon=True
            )
            instance.thread.start()

            # Broadcast start event
            self.socketio.emit('simulation:started', {
                'simulation_id': simulation_id,
                'scenario': {
                    'incident_location': scenario['incident_location'],
                    'num_casualties': scenario['num_casualties'],
                    'num_hospitals': len(scenario['hospitals'])
                },
                'agent_type': instance.agent_type,
                'initial_state': instance.engine.get_state(),
                'initial_metrics': instance.engine.get_metrics()
            })

            logger.info(f"Started simulation {simulation_id}")
            return {'status': 'started', 'simulation_id': simulation_id, 'success': True}

        except Exception as e:
            instance.status = SimulationStatus.ERROR
            instance.error_message = str(e)
            logger.error(f"Failed to start simulation {simulation_id}: {e}")
            return {'error': str(e), 'success': False}

    def pause_simulation(self, simulation_id: str) -> dict:
        """
        Pause a running simulation.

        Args:
            simulation_id: Simulation UUID

        Returns:
            Status dictionary
        """
        instance = self.get_simulation(simulation_id)
        if not instance:
            return {'error': 'Simulation not found', 'success': False}

        if instance.status != SimulationStatus.RUNNING:
            return {'error': 'Simulation is not running', 'success': False}

        instance.status = SimulationStatus.PAUSED

        self.socketio.emit('simulation:paused', {
            'simulation_id': simulation_id,
            'current_time': instance.engine.current_time if instance.engine else 0
        })

        logger.info(f"Paused simulation {simulation_id}")
        return {'status': 'paused', 'success': True}

    def resume_simulation(self, simulation_id: str) -> dict:
        """
        Resume a paused simulation.

        Args:
            simulation_id: Simulation UUID

        Returns:
            Status dictionary
        """
        instance = self.get_simulation(simulation_id)
        if not instance:
            return {'error': 'Simulation not found', 'success': False}

        if instance.status != SimulationStatus.PAUSED:
            return {'error': 'Simulation is not paused', 'success': False}

        instance.status = SimulationStatus.RUNNING

        self.socketio.emit('simulation:resumed', {
            'simulation_id': simulation_id,
            'current_time': instance.engine.current_time if instance.engine else 0
        })

        logger.info(f"Resumed simulation {simulation_id}")
        return {'status': 'resumed', 'success': True}

    def stop_simulation(self, simulation_id: str) -> dict:
        """
        Stop a running or paused simulation.

        Args:
            simulation_id: Simulation UUID

        Returns:
            Status dictionary
        """
        instance = self.get_simulation(simulation_id)
        if not instance:
            return {'error': 'Simulation not found', 'success': False}

        if instance.status in [SimulationStatus.STOPPED, SimulationStatus.COMPLETED]:
            return {'error': f'Simulation already {instance.status.value}', 'success': False}

        instance.status = SimulationStatus.STOPPED
        instance.ended_at = datetime.utcnow()

        # Wait for thread to finish (with timeout)
        if instance.thread and instance.thread.is_alive():
            instance.thread.join(timeout=5)

        self.socketio.emit('simulation:stopped', {
            'simulation_id': simulation_id,
            'final_metrics': instance.engine.get_metrics() if instance.engine else {}
        })

        logger.info(f"Stopped simulation {simulation_id}")
        return {'status': 'stopped', 'success': True}

    def delete_simulation(self, simulation_id: str) -> dict:
        """
        Delete a simulation instance.

        Args:
            simulation_id: Simulation UUID

        Returns:
            Status dictionary
        """
        instance = self.get_simulation(simulation_id)
        if not instance:
            return {'error': 'Simulation not found', 'success': False}

        # Stop if running
        if instance.status in [SimulationStatus.RUNNING, SimulationStatus.PAUSED]:
            self.stop_simulation(simulation_id)

        # Remove from registry
        with self.lock:
            if simulation_id in self.simulations:
                del self.simulations[simulation_id]

        logger.info(f"Deleted simulation {simulation_id}")
        return {'status': 'deleted', 'success': True}

    def set_speed(self, simulation_id: str, speed: float) -> dict:
        """
        Set playback speed for a simulation.

        Args:
            simulation_id: Simulation UUID
            speed: Speed multiplier (1.0 = real-time, 2.0 = 2x, etc.)

        Returns:
            Status dictionary
        """
        instance = self.get_simulation(simulation_id)
        if not instance:
            return {'error': 'Simulation not found', 'success': False}

        if speed <= 0 or speed > 100:
            return {'error': 'Speed must be between 0 and 100', 'success': False}

        instance.speed = speed

        logger.info(f"Set simulation {simulation_id} speed to {speed}x")
        return {'speed': speed, 'success': True}

    def _run_simulation_loop(self, simulation_id: str) -> None:
        """
        Main simulation loop (runs in background thread).

        Args:
            simulation_id: Simulation UUID
        """
        instance = self.get_simulation(simulation_id)
        if not instance or not instance.engine:
            return

        try:
            max_time = 180  # 3 hours max

            while instance.status == SimulationStatus.RUNNING:
                # Check if simulation is done
                if instance.engine.is_done() or instance.engine.current_time >= max_time:
                    break

                # Execute one timestep
                instance.engine.step()
                instance.engine.current_time += 1

                # Update cached metrics
                instance.current_metrics = instance.engine.get_metrics()

                # Broadcast timestep event
                self._broadcast_timestep(simulation_id)

                # Sleep based on speed (1.0 = 1 second per sim minute)
                sleep_time = 1.0 / instance.speed
                time.sleep(sleep_time)

            # Simulation completed
            if instance.status != SimulationStatus.STOPPED:
                instance.status = SimulationStatus.COMPLETED
                instance.ended_at = datetime.utcnow()

                self.socketio.emit('simulation:completed', {
                    'simulation_id': simulation_id,
                    'final_metrics': instance.engine.get_metrics(),
                    'final_time': instance.engine.current_time
                })

                logger.info(f"Simulation {simulation_id} completed at t={instance.engine.current_time}")

        except Exception as e:
            instance.status = SimulationStatus.ERROR
            instance.error_message = str(e)
            instance.ended_at = datetime.utcnow()

            self.socketio.emit('simulation:error', {
                'simulation_id': simulation_id,
                'error': str(e)
            })

            logger.error(f"Simulation {simulation_id} error: {e}", exc_info=True)

    def _on_simulation_event(self, simulation_id: str, event_type: str, data: dict) -> None:
        """
        Handle events from simulation engine.

        Args:
            simulation_id: Simulation UUID
            event_type: Type of event (DISPATCH, PICKUP, DELIVERY, etc.)
            data: Event data
        """
        # Forward specific events to WebSocket
        if event_type in ['DISPATCH', 'PICKUP', 'DELIVERY', 'DEATH']:
            self.socketio.emit(f'simulation:event:{event_type.lower()}', {
                'simulation_id': simulation_id,
                'time': data.get('time', 0),
                **data
            })

    def _broadcast_timestep(self, simulation_id: str) -> None:
        """
        Broadcast current simulation state via WebSocket.

        Args:
            simulation_id: Simulation UUID
        """
        instance = self.get_simulation(simulation_id)
        if not instance or not instance.engine:
            return

        state = instance.engine.get_state()
        metrics = instance.engine.get_metrics()

        self.socketio.emit('simulation:timestep', {
            'simulation_id': simulation_id,
            'time': state['current_time'],
            'casualties': state['casualties'],
            'ambulances': state['ambulances'],
            'hospitals': state['hospitals'],
            'incident_location': state['incident_location'],
            'metrics': metrics
        })

    def _load_scenario(self, scenario_config: dict) -> dict:
        """
        Load or generate scenario based on configuration.

        Args:
            scenario_config: Scenario configuration

        Returns:
            Scenario dictionary
        """
        scenario_type = scenario_config.get('type', 'random')

        if scenario_type == 'file':
            # Load from file
            file_path = scenario_config.get('file')
            if not file_path:
                raise ValueError("scenario_config.file is required for type='file'")

            scenario = ScenarioGenerator.load_scenario(file_path)
            logger.info(f"Loaded scenario from {file_path}")
            return scenario

        elif scenario_type == 'random':
            # Generate random scenario
            region = scenario_config.get('region', 'CA')
            num_casualties = scenario_config.get('num_casualties', 60)
            ambulances_per_hospital = scenario_config.get('ambulances_per_hospital', 2)
            ambulances_per_hospital_variation = scenario_config.get('ambulances_per_hospital_variation', 1)
            field_ambulances = scenario_config.get('field_ambulances', 5)
            field_ambulance_radius_km = scenario_config.get('field_ambulance_radius_km', 10.0)
            seed = scenario_config.get('seed', None)

            # Load hospitals (cached)
            if self._hospitals_cache is None:
                self._hospitals_cache = load_hospitals(region=region)
                logger.info(f"Loaded {len(self._hospitals_cache)} hospitals for region {region}")

            # Calculate region bounds
            from simulator.environment.scenario_generator import calculate_region_bounds
            region_bounds = calculate_region_bounds(self._hospitals_cache)

            # Create generator
            generator = ScenarioGenerator(self._hospitals_cache, region_bounds, seed=seed)

            # Generate scenario
            scenario = generator.generate_scenario(
                num_casualties=num_casualties,
                ambulances_per_hospital=ambulances_per_hospital,
                ambulances_per_hospital_variation=ambulances_per_hospital_variation,
                field_ambulances=field_ambulances,
                field_ambulance_radius_km=field_ambulance_radius_km,
                seed=seed
            )

            logger.info(f"Generated random scenario with {num_casualties} casualties")
            return scenario

        else:
            raise ValueError(f"Unknown scenario type: {scenario_type}")

    def _get_policy(self, agent_type: str) -> Callable:
        """
        Get policy function by agent type.

        Args:
            agent_type: Policy type name

        Returns:
            Policy function

        Raises:
            ValueError: If agent type is unknown
        """
        policy = self.policies.get(agent_type)
        if policy is None:
            raise ValueError(f"Unknown agent type: {agent_type}. Available: {list(self.policies.keys())}")

        return policy
