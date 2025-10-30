"""
Flask Backend Application - RLRapidResponse Visualization Server

Provides REST API and WebSocket interface for controlling and visualizing
mass casualty incident simulations.
"""

from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_cors import CORS
import logging
import sys
import os

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from controllers.simulation_manager import SimulationManager
from controllers.process_manager import ProcessManager
from controllers.scenario_manager import ScenarioManager

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'rlrapidresponse-secret-key-change-in-production'

# Enable CORS for frontend (allow localhost:3000 during development)
CORS(app, resources={
    r"/api/*": {
        "origins": ["http://localhost:3000", "http://127.0.0.1:3000"]
    }
})

# Initialize Socket.IO with CORS
# Use gevent for Python 3.13+ compatibility (eventlet has issues with ssl.wrap_socket)
socketio = SocketIO(
    app,
    cors_allowed_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    async_mode='gevent',
    logger=True,
    engineio_logger=False
)

# Global managers
sim_manager = SimulationManager(socketio)
process_manager = ProcessManager(socketio, PROJECT_ROOT)
scenario_manager = ScenarioManager(PROJECT_ROOT)

logger.info("Flask app initialized")


# ============================================================================
# Health Check & Info
# ============================================================================

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        'status': 'ok',
        'service': 'rlrapidresponse-backend',
        'version': '1.0.0'
    })


@app.route('/api/info', methods=['GET'])
def get_info():
    """Get server information."""
    return jsonify({
        'service': 'RLRapidResponse Backend',
        'version': '1.0.0',
        'available_agents': list(sim_manager.policies.keys()),
        'active_simulations': len([s for s in sim_manager.simulations.values()
                                   if s.status.value in ['running', 'paused']])
    })


# ============================================================================
# Simulation CRUD Endpoints
# ============================================================================

@app.route('/api/simulations', methods=['POST'])
def create_simulation():
    """
    Create a new simulation.

    Request body:
    {
        "scenario_config": {
            "type": "random" | "file",
            "region": "CA" (optional, default: "CA"),
            "num_casualties": 60 (optional),
            "ambulances_per_hospital": 2 (optional),
            "field_ambulances": 5 (optional),
            "file": "path/to/scenario.json" (if type="file")
        },
        "agent_type": "nearest_hospital" | "random" | "triage_priority" | "trauma_matching"
    }

    Returns:
    {
        "simulation_id": "uuid",
        "status": "created"
    }
    """
    try:
        data = request.json

        if not data:
            return jsonify({'error': 'Request body is required'}), 400

        scenario_config = data.get('scenario_config', {'type': 'random'})
        agent_type = data.get('agent_type', 'nearest_hospital')

        # Validate agent type
        if agent_type not in sim_manager.policies:
            return jsonify({
                'error': f'Invalid agent type: {agent_type}',
                'available_agents': list(sim_manager.policies.keys())
            }), 400

        simulation_id = sim_manager.create_simulation(scenario_config, agent_type)

        return jsonify({
            'simulation_id': simulation_id,
            'status': 'created',
            'success': True
        }), 201

    except Exception as e:
        logger.error(f"Error creating simulation: {e}", exc_info=True)
        return jsonify({'error': str(e), 'success': False}), 500


@app.route('/api/simulations', methods=['GET'])
def list_simulations():
    """
    List all simulations.

    Returns:
    {
        "simulations": [
            {
                "id": "uuid",
                "status": "running",
                "agent_type": "nearest_hospital",
                "created_at": "2025-01-01T00:00:00",
                "current_time": 45,
                "metrics": {...}
            }
        ],
        "count": 3
    }
    """
    try:
        simulations = sim_manager.list_simulations()
        return jsonify({
            'simulations': simulations,
            'count': len(simulations),
            'success': True
        })

    except Exception as e:
        logger.error(f"Error listing simulations: {e}", exc_info=True)
        return jsonify({'error': str(e), 'success': False}), 500


@app.route('/api/simulations/<simulation_id>', methods=['GET'])
def get_simulation(simulation_id):
    """
    Get details of a specific simulation.

    Returns:
    {
        "id": "uuid",
        "status": "running",
        "agent_type": "nearest_hospital",
        "current_time": 45,
        "metrics": {...},
        "state": {...}
    }
    """
    try:
        instance = sim_manager.get_simulation(simulation_id)
        if not instance:
            return jsonify({'error': 'Simulation not found', 'success': False}), 404

        response = instance.to_dict()

        # Include current state if engine exists
        if instance.engine:
            response['state'] = instance.engine.get_state()

        return jsonify({**response, 'success': True})

    except Exception as e:
        logger.error(f"Error getting simulation {simulation_id}: {e}", exc_info=True)
        return jsonify({'error': str(e), 'success': False}), 500


@app.route('/api/simulations/<simulation_id>', methods=['DELETE'])
def delete_simulation(simulation_id):
    """
    Delete a simulation.

    Returns:
    {
        "status": "deleted",
        "success": true
    }
    """
    try:
        result = sim_manager.delete_simulation(simulation_id)

        if not result.get('success', True):
            return jsonify(result), 404

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error deleting simulation {simulation_id}: {e}", exc_info=True)
        return jsonify({'error': str(e), 'success': False}), 500


# ============================================================================
# Simulation Control Endpoints
# ============================================================================

@app.route('/api/simulations/<simulation_id>/start', methods=['POST'])
def start_simulation(simulation_id):
    """
    Start a simulation.

    Returns:
    {
        "status": "started",
        "simulation_id": "uuid",
        "success": true
    }
    """
    try:
        result = sim_manager.start_simulation(simulation_id)

        if not result.get('success'):
            return jsonify(result), 400

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error starting simulation {simulation_id}: {e}", exc_info=True)
        return jsonify({'error': str(e), 'success': False}), 500


@app.route('/api/simulations/<simulation_id>/pause', methods=['POST'])
def pause_simulation(simulation_id):
    """
    Pause a running simulation.

    Returns:
    {
        "status": "paused",
        "success": true
    }
    """
    try:
        result = sim_manager.pause_simulation(simulation_id)

        if not result.get('success'):
            return jsonify(result), 400

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error pausing simulation {simulation_id}: {e}", exc_info=True)
        return jsonify({'error': str(e), 'success': False}), 500


@app.route('/api/simulations/<simulation_id>/resume', methods=['POST'])
def resume_simulation(simulation_id):
    """
    Resume a paused simulation.

    Returns:
    {
        "status": "resumed",
        "success": true
    }
    """
    try:
        result = sim_manager.resume_simulation(simulation_id)

        if not result.get('success'):
            return jsonify(result), 400

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error resuming simulation {simulation_id}: {e}", exc_info=True)
        return jsonify({'error': str(e), 'success': False}), 500


@app.route('/api/simulations/<simulation_id>/stop', methods=['POST'])
def stop_simulation(simulation_id):
    """
    Stop a running or paused simulation.

    Returns:
    {
        "status": "stopped",
        "success": true
    }
    """
    try:
        result = sim_manager.stop_simulation(simulation_id)

        if not result.get('success'):
            return jsonify(result), 400

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error stopping simulation {simulation_id}: {e}", exc_info=True)
        return jsonify({'error': str(e), 'success': False}), 500


@app.route('/api/simulations/<simulation_id>/speed', methods=['POST'])
def set_simulation_speed(simulation_id):
    """
    Set playback speed for a simulation.

    Request body:
    {
        "speed": 2.0  # 1.0 = real-time, 2.0 = 2x, etc.
    }

    Returns:
    {
        "speed": 2.0,
        "success": true
    }
    """
    try:
        data = request.json

        if not data or 'speed' not in data:
            return jsonify({'error': 'speed is required', 'success': False}), 400

        speed = float(data['speed'])
        result = sim_manager.set_speed(simulation_id, speed)

        if not result.get('success'):
            return jsonify(result), 400

        return jsonify(result)

    except ValueError:
        return jsonify({'error': 'speed must be a number', 'success': False}), 400
    except Exception as e:
        logger.error(f"Error setting speed for simulation {simulation_id}: {e}", exc_info=True)
        return jsonify({'error': str(e), 'success': False}), 500


# ============================================================================
# Job Management Endpoints (Training/Evaluation)
# ============================================================================

@app.route('/api/jobs', methods=['POST'])
def create_and_start_job():
    """
    Create and start a training/evaluation job.

    Request body:
    {
        "type": "training" | "evaluation" | "simulation",
        "command": "python" | ".venv/bin/python",
        "args": ["simulator/train.py", "--timesteps", "100000"],
        "auto_start": true  (optional, default: true)
    }

    Returns:
    {
        "job_id": "uuid",
        "status": "started",
        "pid": 12345
    }
    """
    try:
        data = request.json

        if not data:
            return jsonify({'error': 'Request body is required'}), 400

        job_type = data.get('type', 'training')
        command = data.get('command', '.venv/bin/python')
        args = data.get('args', [])
        auto_start = data.get('auto_start', True)

        if not args:
            return jsonify({'error': 'args is required'}), 400

        # Create job
        job_id = process_manager.create_job(job_type, command, args)

        # Auto-start if requested
        if auto_start:
            result = process_manager.start_job(job_id)
            if not result.get('success'):
                return jsonify(result), 400
            return jsonify(result), 201
        else:
            return jsonify({
                'job_id': job_id,
                'status': 'created',
                'success': True
            }), 201

    except Exception as e:
        logger.error(f"Error creating job: {e}", exc_info=True)
        return jsonify({'error': str(e), 'success': False}), 500


@app.route('/api/jobs', methods=['GET'])
def list_jobs():
    """
    List all jobs, optionally filtered by status.

    Query params:
        status: Filter by status (optional)

    Returns:
    {
        "jobs": [...],
        "count": 5
    }
    """
    try:
        status_filter = request.args.get('status')
        jobs = process_manager.list_jobs(status_filter=status_filter)

        return jsonify({
            'jobs': jobs,
            'count': len(jobs),
            'success': True
        })

    except Exception as e:
        logger.error(f"Error listing jobs: {e}", exc_info=True)
        return jsonify({'error': str(e), 'success': False}), 500


@app.route('/api/jobs/<job_id>', methods=['GET'])
def get_job(job_id):
    """
    Get job details.

    Returns:
    {
        "id": "uuid",
        "type": "training",
        "status": "running",
        "pid": 12345,
        ...
    }
    """
    try:
        instance = process_manager.get_job(job_id)
        if not instance:
            return jsonify({'error': 'Job not found', 'success': False}), 404

        return jsonify({**instance.to_dict(), 'success': True})

    except Exception as e:
        logger.error(f"Error getting job {job_id}: {e}", exc_info=True)
        return jsonify({'error': str(e), 'success': False}), 500


@app.route('/api/jobs/<job_id>/logs', methods=['GET'])
def get_job_logs(job_id):
    """
    Get recent log lines from a job.

    Query params:
        tail: Number of recent lines to return (default: 100)

    Returns:
    {
        "job_id": "uuid",
        "lines": ["line1", "line2", ...],
        "source": "buffer" | "file"
    }
    """
    try:
        tail = int(request.args.get('tail', 100))
        result = process_manager.get_job_logs(job_id, tail=tail)

        if not result.get('success'):
            return jsonify(result), 404

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error getting logs for job {job_id}: {e}", exc_info=True)
        return jsonify({'error': str(e), 'success': False}), 500


@app.route('/api/jobs/<job_id>/start', methods=['POST'])
def start_job(job_id):
    """
    Start a created job.

    Returns:
    {
        "status": "started",
        "job_id": "uuid",
        "pid": 12345
    }
    """
    try:
        result = process_manager.start_job(job_id)

        if not result.get('success'):
            return jsonify(result), 400

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error starting job {job_id}: {e}", exc_info=True)
        return jsonify({'error': str(e), 'success': False}), 500


@app.route('/api/jobs/<job_id>/kill', methods=['POST'])
def kill_job(job_id):
    """
    Kill a running job.

    Returns:
    {
        "status": "killed",
        "success": true
    }
    """
    try:
        result = process_manager.kill_job(job_id)

        if not result.get('success'):
            return jsonify(result), 400

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error killing job {job_id}: {e}", exc_info=True)
        return jsonify({'error': str(e), 'success': False}), 500


# ============================================================================
# Scenario Management Endpoints
# ============================================================================

@app.route('/api/scenarios', methods=['GET'])
def list_scenarios():
    """
    List all saved scenarios.

    Returns:
    {
        "scenarios": [...],
        "count": 5,
        "success": true
    }
    """
    try:
        scenarios = scenario_manager.list_scenarios()
        return jsonify({
            'scenarios': scenarios,
            'count': len(scenarios),
            'success': True
        })
    except Exception as e:
        logger.error(f"Error listing scenarios: {e}", exc_info=True)
        return jsonify({'error': str(e), 'success': False}), 500


@app.route('/api/scenarios', methods=['POST'])
def generate_scenario():
    """
    Generate a new scenario.

    Request body:
    {
        "region": "CA",
        "num_casualties": 60,
        "ambulances_per_hospital": 2,
        "ambulances_per_hospital_variation": 1,
        "field_ambulances": 5,
        "field_ambulance_radius_km": 10.0,
        "seed": 42,
        "name": "Test Scenario",
        "save": true
    }

    Returns:
    {
        "scenario": {...},
        "preview": {...},
        "success": true
    }
    """
    try:
        data = request.json or {}

        scenario = scenario_manager.generate_scenario(
            region=data.get('region', 'CA'),
            num_casualties=data.get('num_casualties', 60),
            ambulances_per_hospital=data.get('ambulances_per_hospital', 2),
            ambulances_per_hospital_variation=data.get('ambulances_per_hospital_variation', 1),
            field_ambulances=data.get('field_ambulances', 5),
            field_ambulance_radius_km=data.get('field_ambulance_radius_km', 10.0),
            seed=data.get('seed'),
            name=data.get('name'),
            save=data.get('save', True),
            incident_location=data.get('incident_location'),
            manual_ambulances=data.get('manual_ambulances'),
            casualty_distribution_radius=data.get('casualty_distribution_radius', 0.5)
        )

        preview = scenario_manager.get_scenario_preview(scenario)

        return jsonify({
            'scenario': scenario,
            'preview': preview,
            'success': True
        }), 201

    except Exception as e:
        logger.error(f"Error generating scenario: {e}", exc_info=True)
        return jsonify({'error': str(e), 'success': False}), 500


@app.route('/api/scenarios/<scenario_id>', methods=['GET'])
def get_scenario(scenario_id):
    """
    Load a specific scenario.

    Returns:
    {
        "scenario": {...},
        "preview": {...},
        "success": true
    }
    """
    try:
        scenario = scenario_manager.load_scenario(scenario_id)
        if not scenario:
            return jsonify({'error': 'Scenario not found', 'success': False}), 404

        preview = scenario_manager.get_scenario_preview(scenario)

        return jsonify({
            'scenario': scenario,
            'preview': preview,
            'success': True
        })

    except Exception as e:
        logger.error(f"Error loading scenario {scenario_id}: {e}", exc_info=True)
        return jsonify({'error': str(e), 'success': False}), 500


@app.route('/api/scenarios/<scenario_id>', methods=['DELETE'])
def delete_scenario(scenario_id):
    """
    Delete a scenario (only generated scenarios, not benchmarks).

    Returns:
    {
        "status": "deleted",
        "success": true
    }
    """
    try:
        success = scenario_manager.delete_scenario(scenario_id)
        if not success:
            return jsonify({'error': 'Scenario not found or cannot be deleted', 'success': False}), 404

        return jsonify({
            'status': 'deleted',
            'success': True
        })

    except Exception as e:
        logger.error(f"Error deleting scenario {scenario_id}: {e}", exc_info=True)
        return jsonify({'error': str(e), 'success': False}), 500


@app.route('/api/hospitals', methods=['GET'])
def get_hospitals():
    """
    Get hospitals for a region.

    Query params:
        region: Region code (default: CA)

    Returns:
    {
        "hospitals": [...],
        "count": 100,
        "region": "CA",
        "bounds": [min_lat, max_lat, min_lon, max_lon],
        "success": true
    }
    """
    try:
        region = request.args.get('region', 'CA')
        hospitals = scenario_manager.get_hospitals(region)
        bounds = scenario_manager.get_region_bounds(region)

        return jsonify({
            'hospitals': hospitals,
            'count': len(hospitals),
            'region': region,
            'bounds': bounds,
            'success': True
        })

    except Exception as e:
        logger.error(f"Error loading hospitals: {e}", exc_info=True)
        return jsonify({'error': str(e), 'success': False}), 500


# ============================================================================
# WebSocket Event Handlers
# ============================================================================

@socketio.on('connect')
def handle_connect():
    """Handle client connection."""
    client_id = request.sid
    logger.info(f"Client connected: {client_id}")

    emit('connection:success', {
        'status': 'connected',
        'client_id': client_id
    })


@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection."""
    client_id = request.sid
    logger.info(f"Client disconnected: {client_id}")


@socketio.on('subscribe')
def handle_subscribe(data):
    """
    Subscribe to simulation updates.

    Args:
        data: {'simulation_id': 'uuid'}
    """
    simulation_id = data.get('simulation_id')

    if not simulation_id:
        emit('error', {'message': 'simulation_id is required'})
        return

    # Join room for this simulation
    join_room(simulation_id)

    logger.info(f"Client {request.sid} subscribed to simulation {simulation_id}")

    emit('subscribed', {
        'simulation_id': simulation_id,
        'status': 'subscribed'
    })


@socketio.on('unsubscribe')
def handle_unsubscribe(data):
    """
    Unsubscribe from simulation updates.

    Args:
        data: {'simulation_id': 'uuid'}
    """
    simulation_id = data.get('simulation_id')

    if not simulation_id:
        emit('error', {'message': 'simulation_id is required'})
        return

    # Leave room
    leave_room(simulation_id)

    logger.info(f"Client {request.sid} unsubscribed from simulation {simulation_id}")

    emit('unsubscribed', {
        'simulation_id': simulation_id,
        'status': 'unsubscribed'
    })


@socketio.on('ping')
def handle_ping():
    """Handle ping for connection testing."""
    emit('pong', {'timestamp': request.args.get('timestamp')})


# ============================================================================
# Error Handlers
# ============================================================================

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors."""
    return jsonify({
        'error': 'Resource not found',
        'success': False
    }), 404


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors."""
    logger.error(f"Internal server error: {error}", exc_info=True)
    return jsonify({
        'error': 'Internal server error',
        'success': False
    }), 500


# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == '__main__':
    print("=" * 70)
    print("RLRapidResponse Backend Server")
    print("=" * 70)
    print(f"Available agents: {list(sim_manager.policies.keys())}")
    print(f"Starting server on http://0.0.0.0:5000")
    print(f"WebSocket endpoint: ws://0.0.0.0:5000/socket.io/")
    print("=" * 70)

    # Run with eventlet for WebSocket support
    socketio.run(
        app,
        host='0.0.0.0',
        port=5000,
        debug=True,
        use_reloader=False  # Disable reloader to prevent double initialization
    )
