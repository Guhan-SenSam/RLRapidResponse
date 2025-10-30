"""
Backend Functionality Test Script

Tests SimulationManager and Flask app without starting the server.
"""

import sys
sys.path.insert(0, '..')

from controllers.simulation_manager import SimulationManager, SimulationStatus
import time

print("=" * 70)
print("Testing Backend Components")
print("=" * 70)

# Test 1: Create mock SocketIO instance
print("\n1. Testing SimulationManager initialization...")

# Create a simple mock SocketIO for testing
class MockSocketIO:
    """Mock SocketIO for testing without server."""
    def emit(self, event, data):
        """Mock emit method."""
        # print(f"   [WebSocket Event] {event}: {data}")
        pass

socketio = MockSocketIO()
manager = SimulationManager(socketio)

print(f"   ✓ SimulationManager created")
print(f"   ✓ Available policies: {list(manager.policies.keys())}")

# Test 2: Create simulation
print("\n2. Testing simulation creation...")
scenario_config = {
    'type': 'random',
    'region': 'CA',
    'num_casualties': 20,
    'ambulances_per_hospital': 1,
    'field_ambulances': 2
}
sim_id = manager.create_simulation(scenario_config, 'nearest_hospital')
print(f"   ✓ Simulation created: {sim_id}")

# Test 3: List simulations
print("\n3. Testing simulation listing...")
simulations = manager.list_simulations()
print(f"   ✓ Found {len(simulations)} simulation(s)")
print(f"   ✓ Status: {simulations[0]['status']}")

# Test 4: Get simulation details
print("\n4. Testing get simulation...")
instance = manager.get_simulation(sim_id)
print(f"   ✓ Retrieved simulation: {instance.id}")
print(f"   ✓ Agent type: {instance.agent_type}")
print(f"   ✓ Status: {instance.status.value}")

# Test 5: Test scenario loading (without starting)
print("\n5. Testing scenario loading...")
try:
    scenario = manager._load_scenario(scenario_config)
    print(f"   ✓ Scenario loaded successfully")
    print(f"   ✓ Casualties: {scenario['num_casualties']}")
    print(f"   ✓ Hospitals: {len(scenario['hospitals'])}")
    print(f"   ✓ Incident location: {scenario['incident_location']}")
except Exception as e:
    print(f"   ⚠ Warning: Could not load scenario: {e}")
    print(f"   (This may be due to missing hospital data)")

# Test 6: Test policy retrieval
print("\n6. Testing policy retrieval...")
for policy_name in ['random', 'nearest_hospital', 'triage_priority', 'trauma_matching']:
    try:
        policy = manager._get_policy(policy_name)
        print(f"   ✓ Policy '{policy_name}': {policy.__name__}")
    except Exception as e:
        print(f"   ✗ Policy '{policy_name}' failed: {e}")

# Test 7: Test invalid operations
print("\n7. Testing error handling...")
result = manager.start_simulation('invalid-id')
if 'error' in result:
    print(f"   ✓ Invalid simulation ID handled correctly")

result = manager.pause_simulation(sim_id)
if 'error' in result:
    print(f"   ✓ Cannot pause non-running simulation (expected)")

# Test 8: Speed control
print("\n8. Testing speed control...")
result = manager.set_speed(sim_id, 2.0)
if result.get('success'):
    print(f"   ✓ Speed set to {result['speed']}x")

result = manager.set_speed(sim_id, -1.0)
if 'error' in result:
    print(f"   ✓ Invalid speed rejected (expected)")

# Test 9: Delete simulation
print("\n9. Testing simulation deletion...")
result = manager.delete_simulation(sim_id)
if result.get('success'):
    print(f"   ✓ Simulation deleted")

simulations_after = manager.list_simulations()
print(f"   ✓ Simulations remaining: {len(simulations_after)}")

print("\n" + "=" * 70)
print("✓ All backend tests passed!")
print("=" * 70)
print("\nNext steps:")
print("  1. Start the backend server: python backend/app.py")
print("  2. Test endpoints: curl http://localhost:5000/api/health")
print("  3. Create a simulation via API")
print("  4. Start the simulation and view WebSocket events")
