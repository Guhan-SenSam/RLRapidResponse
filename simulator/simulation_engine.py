"""
Core Simulation Engine - Step 1.5

Discrete-event simulator for mass casualty incident response.
Time advances in 1-minute intervals.
"""

from typing import Dict, List, Callable, Optional, Any
import copy
import sys
import os

# Add project root to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from simulator.environment.scenario_generator import ScenarioGenerator
from simulator.environment.patient_model import PatientModel
from simulator.environment.routing import euclidean_distance, euclidean_travel_time


class SimulationEngine:
    """
    Discrete-event simulation engine for MCI response.

    Manages ambulances, casualties, and hospital state over discrete time steps.
    Supports flexible ambulance actions: dispatch, reposition, return to base.
    """

    def __init__(self, scenario: Dict, policy: Callable):
        """
        Initialize simulation with scenario and policy.

        Args:
            scenario: Scenario dict from ScenarioGenerator (with ambulance_config)
            policy: Policy function that takes state dict and returns actions dict
        """
        self.scenario = scenario
        self.policy = policy
        self.current_time = 0

        # Spawn ambulances lazily from config
        generator = ScenarioGenerator([], (0, 0, 0, 0))  # Dummy init
        self.ambulances = generator.spawn_ambulances(
            scenario['incident_location'],
            scenario['ambulance_config'],
            scenario['hospitals']
        )

        # Convert ambulances to runtime state objects
        self._initialize_ambulances()

        # Initialize casualties with PatientModel
        self._initialize_casualties()

        # Copy hospitals reference
        self.hospitals = scenario['hospitals']

        # Event log for analysis
        self.event_log = []

        # Metrics tracking
        self.metrics = {
            'deaths': 0,
            'transported': 0,
            'total_casualties': len(self.casualties),
            'casualties_waiting': 0,
            'avg_response_time': 0.0,
            'total_response_time': 0.0,
            'pickups': 0
        }

        # Event listeners (for optional WebSocket integration later)
        self.event_listeners = []

    def _initialize_ambulances(self) -> None:
        """Convert spawned ambulances to runtime state objects."""
        for amb in self.ambulances:
            amb['status'] = 'IDLE'
            amb['patient_onboard'] = None  # None or casualty_id
            amb['target_lat'] = None
            amb['target_lon'] = None
            amb['time_to_target'] = 0.0
            amb['destination_hospital_id'] = None
            amb['action_type'] = None  # Current action being executed

    def _initialize_casualties(self) -> None:
        """Initialize casualties with PatientModel instances."""
        self.casualties = []

        for casualty_data in self.scenario['casualties']:
            casualty = {
                'id': casualty_data['id'],
                'lat': casualty_data['lat'],
                'lon': casualty_data['lon'],
                'triage': casualty_data['triage'],
                'patient': PatientModel(casualty_data['triage']),
                'status': 'WAITING',  # WAITING, ASSIGNED, ENROUTE, DELIVERED
                'assigned_ambulance_id': None,
                'pickup_time': None,
                'delivery_time': None
            }
            self.casualties.append(casualty)

    def run(self, max_time_minutes: int = 180) -> None:
        """
        Run simulation until completion or max time.

        Args:
            max_time_minutes: Maximum simulation time in minutes (default 180 = 3 hours)
        """
        while self.current_time < max_time_minutes and not self.is_done():
            self.step()
            self.current_time += 1

        # Final metrics calculation
        self._calculate_final_metrics()

        # Log simulation end
        self._log_event('SIMULATION_END', {
            'final_time': self.current_time,
            'deaths': self.metrics['deaths'],
            'transported': self.metrics['transported']
        })

    def step(self) -> None:
        """
        Execute one discrete time step (1 minute).

        Order of operations:
        1. Update patient health (deterioration)
        2. Update ambulance movements
        3. Check for arrivals (pickups/deliveries)
        4. Get policy actions for IDLE ambulances
        5. Execute actions
        6. Update metrics
        """
        # 1. Update all patient health
        self._update_patient_health()

        # 2. Update ambulance movements
        self._update_ambulance_movements()

        # 3. Check for arrivals
        self._check_arrivals()

        # 4. Get actions from policy for IDLE ambulances
        state = self.get_state()
        actions = self.policy(state)

        # 5. Execute actions
        if actions:
            self._execute_actions(actions)

        # 6. Update metrics
        self._update_metrics()

    def _update_patient_health(self) -> None:
        """Update health of all casualties."""
        for casualty in self.casualties:
            if casualty['patient'].is_alive:
                casualty['patient'].update(1)  # 1 minute

                # Check for death
                if not casualty['patient'].is_alive:
                    casualty['status'] = 'DECEASED'
                    self.metrics['deaths'] += 1
                    self._log_event('DEATH', {
                        'casualty_id': casualty['id'],
                        'triage': casualty['triage'],
                        'time': self.current_time
                    })

    def _update_ambulance_movements(self) -> None:
        """Update positions of moving ambulances."""
        for amb in self.ambulances:
            if amb['status'] in ['MOVING_TO_CASUALTY', 'MOVING_TO_HOSPITAL', 'MOVING_TO_LOCATION', 'RETURNING_TO_BASE']:
                amb['time_to_target'] -= 1

                # Update position (linear interpolation)
                if amb['time_to_target'] > 0:
                    # Still moving
                    pass  # Position updates handled on arrival
                elif amb['time_to_target'] <= 0:
                    # Arrival handled in _check_arrivals
                    amb['time_to_target'] = 0

    def _check_arrivals(self) -> None:
        """Check for ambulance arrivals at destinations."""
        for amb in self.ambulances:
            if amb['time_to_target'] <= 0 and amb['status'] != 'IDLE':

                if amb['status'] == 'MOVING_TO_CASUALTY':
                    # Arrived at casualty - pickup
                    self._execute_pickup(amb)

                elif amb['status'] == 'MOVING_TO_HOSPITAL':
                    # Arrived at hospital - delivery
                    self._execute_delivery(amb)

                elif amb['status'] in ['MOVING_TO_LOCATION', 'RETURNING_TO_BASE']:
                    # Arrived at repositioning target
                    amb['lat'] = amb['target_lat']
                    amb['lon'] = amb['target_lon']
                    amb['status'] = 'IDLE'
                    amb['target_lat'] = None
                    amb['target_lon'] = None
                    amb['action_type'] = None

                    self._log_event('REPOSITIONED', {
                        'ambulance_id': amb['id'],
                        'location': (amb['lat'], amb['lon']),
                        'time': self.current_time
                    })

    def _execute_pickup(self, ambulance: Dict) -> None:
        """Execute casualty pickup."""
        casualty_id = ambulance['patient_onboard']
        casualty = next(c for c in self.casualties if c['id'] == casualty_id)

        # Apply ambulance treatment
        casualty['patient'].apply_treatment('PICKUP')
        casualty['status'] = 'ENROUTE'
        casualty['pickup_time'] = self.current_time

        # Calculate response time (time from start to pickup)
        response_time = self.current_time
        self.metrics['total_response_time'] += response_time
        self.metrics['pickups'] += 1

        # Update ambulance position
        ambulance['lat'] = casualty['lat']
        ambulance['lon'] = casualty['lon']

        # Start moving to hospital
        hospital = next(h for h in self.hospitals if h['id'] == ambulance['destination_hospital_id'])
        travel_time = euclidean_travel_time(
            ambulance['lat'], ambulance['lon'],
            hospital['lat'], hospital['lon']
        )

        ambulance['status'] = 'MOVING_TO_HOSPITAL'
        ambulance['target_lat'] = hospital['lat']
        ambulance['target_lon'] = hospital['lon']
        ambulance['time_to_target'] = travel_time

        self._log_event('PICKUP', {
            'ambulance_id': ambulance['id'],
            'casualty_id': casualty_id,
            'triage': casualty['triage'],
            'response_time': response_time,
            'time': self.current_time
        })

    def _execute_delivery(self, ambulance: Dict) -> None:
        """Execute hospital delivery."""
        casualty_id = ambulance['patient_onboard']
        casualty = next(c for c in self.casualties if c['id'] == casualty_id)
        hospital = next(h for h in self.hospitals if h['id'] == ambulance['destination_hospital_id'])

        # Apply hospital treatment (stops deterioration)
        casualty['patient'].apply_treatment('HOSPITAL')
        casualty['status'] = 'DELIVERED'
        casualty['delivery_time'] = self.current_time

        # Update metrics
        self.metrics['transported'] += 1

        # Update ambulance - stays at hospital, becomes IDLE
        ambulance['lat'] = hospital['lat']
        ambulance['lon'] = hospital['lon']
        ambulance['status'] = 'IDLE'
        ambulance['patient_onboard'] = None
        ambulance['destination_hospital_id'] = None
        ambulance['target_lat'] = None
        ambulance['target_lon'] = None
        ambulance['action_type'] = None

        self._log_event('DELIVERY', {
            'ambulance_id': ambulance['id'],
            'casualty_id': casualty_id,
            'hospital_id': hospital['id'],
            'triage': casualty['triage'],
            'time': self.current_time
        })

    def _execute_actions(self, actions: Dict[int, Dict]) -> None:
        """
        Execute policy actions for ambulances.

        Args:
            actions: Dict mapping ambulance_id to action dict
                Action dict format:
                {
                    'action_type': 'DISPATCH_TO_CASUALTY' | 'MOVE_TO_LOCATION' | 'RETURN_TO_BASE' | 'WAIT',
                    'casualty_id': int (for DISPATCH_TO_CASUALTY),
                    'hospital_id': str (for DISPATCH_TO_CASUALTY),
                    'target_lat': float (for MOVE_TO_LOCATION),
                    'target_lon': float (for MOVE_TO_LOCATION)
                }
        """
        for ambulance_id, action in actions.items():
            ambulance = next((a for a in self.ambulances if a['id'] == ambulance_id), None)

            if ambulance is None or ambulance['status'] != 'IDLE':
                continue  # Invalid ambulance or not idle

            action_type = action.get('action_type', 'WAIT')

            if action_type == 'DISPATCH_TO_CASUALTY':
                self._action_dispatch(ambulance, action)

            elif action_type == 'MOVE_TO_LOCATION':
                self._action_move_to_location(ambulance, action)

            elif action_type == 'RETURN_TO_BASE':
                self._action_return_to_base(ambulance)

            elif action_type == 'WAIT':
                pass  # Do nothing

    def _action_dispatch(self, ambulance: Dict, action: Dict) -> None:
        """Dispatch ambulance to pick up casualty and deliver to hospital."""
        casualty_id = action.get('casualty_id')
        hospital_id = action.get('hospital_id')

        # Validate casualty
        casualty = next((c for c in self.casualties if c['id'] == casualty_id), None)
        if casualty is None or casualty['status'] != 'WAITING':
            return  # Invalid or already assigned

        # Mark casualty as assigned
        casualty['status'] = 'ASSIGNED'
        casualty['assigned_ambulance_id'] = ambulance['id']

        # Calculate travel time to casualty
        travel_time = euclidean_travel_time(
            ambulance['lat'], ambulance['lon'],
            casualty['lat'], casualty['lon']
        )

        # Update ambulance state
        ambulance['status'] = 'MOVING_TO_CASUALTY'
        ambulance['patient_onboard'] = casualty_id
        ambulance['destination_hospital_id'] = hospital_id
        ambulance['target_lat'] = casualty['lat']
        ambulance['target_lon'] = casualty['lon']
        ambulance['time_to_target'] = travel_time
        ambulance['action_type'] = 'DISPATCH_TO_CASUALTY'

        self._log_event('DISPATCH', {
            'ambulance_id': ambulance['id'],
            'casualty_id': casualty_id,
            'hospital_id': hospital_id,
            'travel_time': travel_time,
            'time': self.current_time
        })

    def _action_move_to_location(self, ambulance: Dict, action: Dict) -> None:
        """Reposition ambulance to strategic location."""
        target_lat = action.get('target_lat')
        target_lon = action.get('target_lon')

        if target_lat is None or target_lon is None:
            return

        # Calculate travel time
        travel_time = euclidean_travel_time(
            ambulance['lat'], ambulance['lon'],
            target_lat, target_lon
        )

        # Update ambulance state
        ambulance['status'] = 'MOVING_TO_LOCATION'
        ambulance['target_lat'] = target_lat
        ambulance['target_lon'] = target_lon
        ambulance['time_to_target'] = travel_time
        ambulance['action_type'] = 'MOVE_TO_LOCATION'

        self._log_event('MOVE_TO_LOCATION', {
            'ambulance_id': ambulance['id'],
            'target': (target_lat, target_lon),
            'travel_time': travel_time,
            'time': self.current_time
        })

    def _action_return_to_base(self, ambulance: Dict) -> None:
        """Return ambulance to its base hospital."""
        base_hospital_id = ambulance.get('base_hospital_id')

        if base_hospital_id is None:
            # Field unit with no base - do nothing
            return

        # Find base hospital
        base_hospital = next((h for h in self.hospitals if h['id'] == base_hospital_id), None)
        if base_hospital is None:
            return

        # Calculate travel time
        travel_time = euclidean_travel_time(
            ambulance['lat'], ambulance['lon'],
            base_hospital['lat'], base_hospital['lon']
        )

        # Update ambulance state
        ambulance['status'] = 'RETURNING_TO_BASE'
        ambulance['target_lat'] = base_hospital['lat']
        ambulance['target_lon'] = base_hospital['lon']
        ambulance['time_to_target'] = travel_time
        ambulance['action_type'] = 'RETURN_TO_BASE'

        self._log_event('RETURN_TO_BASE', {
            'ambulance_id': ambulance['id'],
            'base_hospital_id': base_hospital_id,
            'travel_time': travel_time,
            'time': self.current_time
        })

    def _update_metrics(self) -> None:
        """Update simulation metrics."""
        self.metrics['casualties_waiting'] = sum(
            1 for c in self.casualties
            if c['status'] == 'WAITING' and c['patient'].is_alive
        )

    def _calculate_final_metrics(self) -> None:
        """Calculate final metrics at simulation end."""
        if self.metrics['pickups'] > 0:
            self.metrics['avg_response_time'] = self.metrics['total_response_time'] / self.metrics['pickups']
        else:
            self.metrics['avg_response_time'] = 0.0

    def is_done(self) -> bool:
        """
        Check if simulation is complete.

        Returns:
            True if all casualties are delivered or deceased
        """
        for casualty in self.casualties:
            if casualty['patient'].is_alive and casualty['status'] not in ['DELIVERED', 'DECEASED']:
                return False
        return True

    def get_state(self) -> Dict:
        """
        Get current simulation state for policy.

        Returns:
            State dict with casualties, ambulances, hospitals, time
        """
        return {
            'casualties': [
                {
                    'id': c['id'],
                    'lat': c['lat'],
                    'lon': c['lon'],
                    'triage': c['triage'],
                    'health': c['patient'].health,
                    'is_alive': c['patient'].is_alive,
                    'status': c['status'],
                    'assigned_ambulance_id': c['assigned_ambulance_id']
                }
                for c in self.casualties
            ],
            'ambulances': [
                {
                    'id': a['id'],
                    'lat': a['lat'],
                    'lon': a['lon'],
                    'status': a['status'],
                    'base_hospital_id': a['base_hospital_id'],
                    'type': a['type'],
                    'patient_onboard': a['patient_onboard']
                }
                for a in self.ambulances
            ],
            'hospitals': self.hospitals,
            'current_time': self.current_time,
            'incident_location': self.scenario['incident_location']
        }

    def get_metrics(self) -> Dict:
        """Get current simulation metrics."""
        return copy.deepcopy(self.metrics)

    def _log_event(self, event_type: str, data: Dict) -> None:
        """Log simulation event."""
        event = {
            'type': event_type,
            'time': self.current_time,
            'data': data
        }
        self.event_log.append(event)

        # Emit to listeners (for WebSocket integration later)
        self.emit_event(event_type, data)

    def register_listener(self, callback: Callable) -> None:
        """Register event listener for WebSocket integration."""
        self.event_listeners.append(callback)

    def emit_event(self, event_type: str, data: Dict) -> None:
        """Emit event to all registered listeners."""
        for listener in self.event_listeners:
            listener(event_type, data)


if __name__ == '__main__':
    # Test simulation engine
    print("Testing Simulation Engine...")
    print("=" * 60)

    # Create test scenario
    from simulator.environment.hospital_loader import load_hospitals
    from simulator.environment.scenario_generator import calculate_region_bounds

    print("\n1. Loading test scenario...")
    hospitals = load_hospitals(region='CA')[:10]  # Use only 10 hospitals for testing
    region_bounds = calculate_region_bounds(hospitals)
    generator = ScenarioGenerator(hospitals, region_bounds, seed=42)

    scenario = generator.generate_scenario(
        num_casualties=20,
        ambulances_per_hospital=1,
        ambulances_per_hospital_variation=0,
        field_ambulances=2,
        field_ambulance_radius_km=5.0,
        seed=123
    )

    print(f"   Scenario: {scenario['num_casualties']} casualties, 10 hospitals")
    print(f"   Ambulance config: {scenario['ambulance_config']}")

    # Define simple nearest-hospital policy
    def nearest_hospital_policy(state):
        """Simple policy: dispatch to nearest waiting casualty, nearest hospital."""
        actions = {}

        idle_ambulances = [a for a in state['ambulances'] if a['status'] == 'IDLE']
        waiting_casualties = [c for c in state['casualties'] if c['status'] == 'WAITING' and c['is_alive']]

        for amb in idle_ambulances[:min(len(idle_ambulances), len(waiting_casualties))]:
            if not waiting_casualties:
                break

            # Find nearest waiting casualty
            nearest_casualty = min(
                waiting_casualties,
                key=lambda c: euclidean_distance(amb['lat'], amb['lon'], c['lat'], c['lon'])
            )

            # Find nearest hospital
            nearest_hospital = min(
                state['hospitals'],
                key=lambda h: euclidean_distance(nearest_casualty['lat'], nearest_casualty['lon'], h['lat'], h['lon'])
            )

            actions[amb['id']] = {
                'action_type': 'DISPATCH_TO_CASUALTY',
                'casualty_id': nearest_casualty['id'],
                'hospital_id': nearest_hospital['id']
            }

            # Remove from waiting list
            waiting_casualties.remove(nearest_casualty)

        return actions

    # Run simulation
    print("\n2. Running simulation...")
    engine = SimulationEngine(scenario, nearest_hospital_policy)

    initial_ambulances = len(engine.ambulances)
    print(f"   Spawned {initial_ambulances} ambulances")
    print(f"   Hospital-based: {sum(1 for a in engine.ambulances if a['type'] == 'HOSPITAL_BASED')}")
    print(f"   Field units: {sum(1 for a in engine.ambulances if a['type'] == 'FIELD_UNIT')}")

    engine.run(max_time_minutes=120)

    print(f"\n3. Simulation completed at t={engine.current_time} minutes")
    metrics = engine.get_metrics()
    print(f"   Deaths: {metrics['deaths']}")
    print(f"   Transported: {metrics['transported']}")
    print(f"   Avg response time: {metrics['avg_response_time']:.2f} minutes")
    print(f"   Casualties waiting: {metrics['casualties_waiting']}")

    # Check event log
    print(f"\n4. Event log analysis...")
    print(f"   Total events: {len(engine.event_log)}")

    event_types = {}
    for event in engine.event_log:
        event_types[event['type']] = event_types.get(event['type'], 0) + 1

    for event_type, count in sorted(event_types.items()):
        print(f"   {event_type}: {count}")

    # Test strategic repositioning
    print("\n5. Testing strategic repositioning...")

    repositioned = {'count': 0}

    def repositioning_policy(state):
        """Policy that repositions ambulances strategically."""
        actions = {}
        idle_ambulances = [a for a in state['ambulances'] if a['status'] == 'IDLE']

        # Reposition first idle ambulance to incident location (only once)
        if idle_ambulances and repositioned['count'] == 0:
            actions[idle_ambulances[0]['id']] = {
                'action_type': 'MOVE_TO_LOCATION',
                'target_lat': state['incident_location'][0],
                'target_lon': state['incident_location'][1]
            }
            repositioned['count'] += 1

        return actions

    scenario2 = generator.generate_scenario(
        num_casualties=5,
        ambulances_per_hospital=1,
        ambulances_per_hospital_variation=0,
        field_ambulances=1,
        seed=456
    )

    engine2 = SimulationEngine(scenario2, repositioning_policy)
    engine2.run(max_time_minutes=60)

    reposition_events = [e for e in engine2.event_log if e['type'] in ['MOVE_TO_LOCATION', 'REPOSITIONED']]
    print(f"   Repositioning events: {len(reposition_events)}")

    if len(reposition_events) >= 2:  # Should have MOVE_TO_LOCATION and REPOSITIONED
        print("   ✓ PASS: Strategic repositioning works")
    else:
        print("   ⚠ WARNING: Repositioning may not have completed fully")

    print("\n" + "=" * 60)
    print("✓ Simulation engine tests completed!")
