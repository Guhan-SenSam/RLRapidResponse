"""
Process Manager - Training/Evaluation Job Controller

Manages long-running training and evaluation jobs as independent subprocesses.
Provides real-time log streaming and process monitoring.
"""

import subprocess
import threading
import uuid
import json
import os
import time
import signal
import logging
from datetime import datetime
from typing import Dict, Optional, List
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


class ProcessStatus(Enum):
    """Process execution status."""
    CREATED = "created"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    KILLED = "killed"


class ProcessType(Enum):
    """Type of process."""
    TRAINING = "training"
    EVALUATION = "evaluation"
    SIMULATION = "simulation"


class ProcessInstance:
    """
    Represents a single training/evaluation job.

    Attributes:
        id: Unique job identifier
        process_type: Type of job (training/evaluation)
        command: Command to execute
        args: Command arguments
        status: Current process status
        pid: Process ID (None if not started)
        created_at: Creation timestamp
        started_at: Start timestamp
        ended_at: End timestamp
        exit_code: Process exit code
        log_file: Path to log file
        output_buffer: Recent output lines (for WebSocket)
    """

    def __init__(self, job_id: str, process_type: str, command: str, args: List[str]):
        self.id = job_id
        self.process_type = process_type
        self.command = command
        self.args = args
        self.status = ProcessStatus.CREATED
        self.pid: Optional[int] = None
        self.process: Optional[subprocess.Popen] = None
        self.created_at = datetime.utcnow()
        self.started_at: Optional[datetime] = None
        self.ended_at: Optional[datetime] = None
        self.exit_code: Optional[int] = None
        self.log_file: Optional[str] = None
        self.output_buffer: List[str] = []  # Last 1000 lines
        self.max_buffer_size = 1000

    def to_dict(self) -> Dict:
        """Convert to dictionary for API responses."""
        return {
            'id': self.id,
            'process_type': self.process_type,
            'command': self.command,
            'args': self.args,
            'status': self.status.value,
            'pid': self.pid,
            'created_at': self.created_at.isoformat(),
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'ended_at': self.ended_at.isoformat() if self.ended_at else None,
            'exit_code': self.exit_code,
            'log_file': self.log_file
        }

    def add_output_line(self, line: str):
        """Add line to output buffer (ring buffer)."""
        self.output_buffer.append(line)
        if len(self.output_buffer) > self.max_buffer_size:
            self.output_buffer.pop(0)


class ProcessManager:
    """
    Manages training/evaluation processes as independent subprocesses.

    Features:
    - Spawn processes with real-time log streaming
    - Process persistence (survive backend restarts)
    - Monitor multiple concurrent jobs
    - Attach to existing processes
    """

    def __init__(self, socketio, project_root: str, state_file: str = "backend/process_state.json"):
        """
        Initialize process manager.

        Args:
            socketio: Flask-SocketIO instance for broadcasting
            project_root: Absolute path to project root
            state_file: Path to state persistence file
        """
        self.socketio = socketio
        self.project_root = project_root
        self.state_file = os.path.join(project_root, state_file)
        self.log_dir = os.path.join(project_root, "logs", "jobs")
        self.processes: Dict[str, ProcessInstance] = {}
        self.lock = threading.Lock()

        # Ensure log directory exists
        os.makedirs(self.log_dir, exist_ok=True)

        # Load existing processes
        self._load_state()

        logger.info(f"ProcessManager initialized (project_root: {project_root})")

    def create_job(self, process_type: str, command: str, args: List[str]) -> str:
        """
        Create a new job (doesn't start it yet).

        Args:
            process_type: 'training' | 'evaluation' | 'simulation'
            command: Command to execute (e.g., 'python')
            args: Command arguments (e.g., ['simulator/train.py', '--timesteps', '100000'])

        Returns:
            Job ID
        """
        job_id = str(uuid.uuid4())
        instance = ProcessInstance(job_id, process_type, command, args)

        # Set up log file
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        instance.log_file = os.path.join(
            self.log_dir,
            f"{process_type}_{timestamp}_{job_id[:8]}.log"
        )

        with self.lock:
            self.processes[job_id] = instance

        self._save_state()
        logger.info(f"Created job {job_id} ({process_type}): {command} {' '.join(args)}")

        return job_id

    def start_job(self, job_id: str) -> Dict:
        """
        Start a job as subprocess.

        Args:
            job_id: Job UUID

        Returns:
            Status dictionary
        """
        instance = self.processes.get(job_id)
        if not instance:
            return {'error': 'Job not found', 'success': False}

        if instance.status != ProcessStatus.CREATED:
            return {'error': f'Job is {instance.status.value}', 'success': False}

        try:
            # Prepare command
            full_command = [instance.command] + instance.args

            # Open log file
            log_file_handle = open(instance.log_file, 'w', buffering=1)

            # Start process
            instance.process = subprocess.Popen(
                full_command,
                cwd=self.project_root,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  # Merge stderr into stdout
                text=True,
                bufsize=1,  # Line buffered
                env={**os.environ, 'PYTHONUNBUFFERED': '1'}  # Disable Python buffering
            )

            instance.pid = instance.process.pid
            instance.status = ProcessStatus.RUNNING
            instance.started_at = datetime.utcnow()

            # Start output streaming thread
            thread = threading.Thread(
                target=self._stream_output,
                args=(job_id, instance.process.stdout, log_file_handle),
                daemon=True
            )
            thread.start()

            # Start process monitor thread
            monitor_thread = threading.Thread(
                target=self._monitor_process,
                args=(job_id,),
                daemon=True
            )
            monitor_thread.start()

            self._save_state()

            # Broadcast start event
            self.socketio.emit('job:started', {
                'job_id': job_id,
                'pid': instance.pid,
                'process_type': instance.process_type,
                'command': f"{instance.command} {' '.join(instance.args)}"
            })

            logger.info(f"Started job {job_id} (PID: {instance.pid})")
            return {'status': 'started', 'job_id': job_id, 'pid': instance.pid, 'success': True}

        except Exception as e:
            instance.status = ProcessStatus.FAILED
            instance.exit_code = -1
            logger.error(f"Failed to start job {job_id}: {e}", exc_info=True)
            return {'error': str(e), 'success': False}

    def _stream_output(self, job_id: str, stdout, log_file_handle):
        """
        Stream process output to WebSocket and log file.

        Args:
            job_id: Job UUID
            stdout: Process stdout pipe
            log_file_handle: Open file handle for logging
        """
        instance = self.processes.get(job_id)
        if not instance:
            return

        try:
            for line in iter(stdout.readline, ''):
                if not line:
                    break

                line = line.rstrip('\n')

                # Write to log file
                log_file_handle.write(line + '\n')
                log_file_handle.flush()

                # Add to buffer
                instance.add_output_line(line)

                # Broadcast via WebSocket
                self.socketio.emit('job:output', {
                    'job_id': job_id,
                    'line': line,
                    'timestamp': datetime.utcnow().isoformat()
                })

        except Exception as e:
            logger.error(f"Error streaming output for job {job_id}: {e}")

        finally:
            stdout.close()
            log_file_handle.close()

    def _monitor_process(self, job_id: str):
        """
        Monitor process completion.

        Args:
            job_id: Job UUID
        """
        instance = self.processes.get(job_id)
        if not instance or not instance.process:
            return

        # Wait for process to complete
        exit_code = instance.process.wait()

        instance.exit_code = exit_code
        instance.ended_at = datetime.utcnow()

        if exit_code == 0:
            instance.status = ProcessStatus.COMPLETED
            logger.info(f"Job {job_id} completed successfully")
        else:
            instance.status = ProcessStatus.FAILED
            logger.error(f"Job {job_id} failed with exit code {exit_code}")

        self._save_state()

        # Broadcast completion
        self.socketio.emit('job:completed', {
            'job_id': job_id,
            'exit_code': exit_code,
            'status': instance.status.value,
            'duration': (instance.ended_at - instance.started_at).total_seconds() if instance.started_at else None
        })

    def kill_job(self, job_id: str) -> Dict:
        """
        Kill a running job.

        Args:
            job_id: Job UUID

        Returns:
            Status dictionary
        """
        instance = self.processes.get(job_id)
        if not instance:
            return {'error': 'Job not found', 'success': False}

        if instance.status != ProcessStatus.RUNNING:
            return {'error': 'Job is not running', 'success': False}

        if not instance.process or not instance.pid:
            return {'error': 'No process to kill', 'success': False}

        try:
            # Try graceful termination first
            instance.process.terminate()
            time.sleep(1)

            # Force kill if still alive
            if instance.process.poll() is None:
                instance.process.kill()

            instance.status = ProcessStatus.KILLED
            instance.ended_at = datetime.utcnow()
            instance.exit_code = -9

            self._save_state()

            self.socketio.emit('job:killed', {
                'job_id': job_id,
                'pid': instance.pid
            })

            logger.info(f"Killed job {job_id} (PID: {instance.pid})")
            return {'status': 'killed', 'success': True}

        except Exception as e:
            logger.error(f"Failed to kill job {job_id}: {e}", exc_info=True)
            return {'error': str(e), 'success': False}

    def get_job(self, job_id: str) -> Optional[ProcessInstance]:
        """Get job by ID."""
        return self.processes.get(job_id)

    def list_jobs(self, status_filter: Optional[str] = None) -> List[Dict]:
        """
        List all jobs, optionally filtered by status.

        Args:
            status_filter: Optional status to filter by

        Returns:
            List of job dictionaries
        """
        with self.lock:
            jobs = [job.to_dict() for job in self.processes.values()]

        if status_filter:
            jobs = [j for j in jobs if j['status'] == status_filter]

        # Sort by created_at descending
        jobs.sort(key=lambda x: x['created_at'], reverse=True)

        return jobs

    def get_job_logs(self, job_id: str, tail: int = 100) -> Dict:
        """
        Get recent log lines from a job.

        Args:
            job_id: Job UUID
            tail: Number of recent lines to return

        Returns:
            Dictionary with log lines
        """
        instance = self.processes.get(job_id)
        if not instance:
            return {'error': 'Job not found', 'success': False}

        # Return from buffer first (faster)
        if instance.output_buffer:
            lines = instance.output_buffer[-tail:]
            return {
                'job_id': job_id,
                'lines': lines,
                'source': 'buffer',
                'success': True
            }

        # Fall back to reading log file
        if instance.log_file and os.path.exists(instance.log_file):
            try:
                with open(instance.log_file, 'r') as f:
                    lines = f.readlines()
                    lines = [line.rstrip('\n') for line in lines[-tail:]]

                return {
                    'job_id': job_id,
                    'lines': lines,
                    'source': 'file',
                    'success': True
                }
            except Exception as e:
                logger.error(f"Failed to read log file for job {job_id}: {e}")
                return {'error': str(e), 'success': False}

        return {'job_id': job_id, 'lines': [], 'source': 'none', 'success': True}

    def _save_state(self):
        """Save process state to disk."""
        try:
            state = {
                'processes': {
                    job_id: {
                        'id': job.id,
                        'process_type': job.process_type,
                        'command': job.command,
                        'args': job.args,
                        'status': job.status.value,
                        'pid': job.pid,
                        'created_at': job.created_at.isoformat(),
                        'started_at': job.started_at.isoformat() if job.started_at else None,
                        'ended_at': job.ended_at.isoformat() if job.ended_at else None,
                        'exit_code': job.exit_code,
                        'log_file': job.log_file
                    }
                    for job_id, job in self.processes.items()
                }
            }

            with open(self.state_file, 'w') as f:
                json.dump(state, f, indent=2)

        except Exception as e:
            logger.error(f"Failed to save state: {e}")

    def _load_state(self):
        """Load process state from disk."""
        if not os.path.exists(self.state_file):
            logger.info("No state file found, starting fresh")
            return

        try:
            with open(self.state_file, 'r') as f:
                state = json.load(f)

            for job_id, job_data in state.get('processes', {}).items():
                instance = ProcessInstance(
                    job_data['id'],
                    job_data['process_type'],
                    job_data['command'],
                    job_data['args']
                )
                instance.status = ProcessStatus(job_data['status'])
                instance.pid = job_data.get('pid')
                instance.created_at = datetime.fromisoformat(job_data['created_at'])
                instance.started_at = datetime.fromisoformat(job_data['started_at']) if job_data.get('started_at') else None
                instance.ended_at = datetime.fromisoformat(job_data['ended_at']) if job_data.get('ended_at') else None
                instance.exit_code = job_data.get('exit_code')
                instance.log_file = job_data.get('log_file')

                # Check if process is still running
                if instance.status == ProcessStatus.RUNNING and instance.pid:
                    if not self._is_process_alive(instance.pid):
                        instance.status = ProcessStatus.FAILED
                        instance.exit_code = -1
                        logger.warning(f"Process {job_id} (PID {instance.pid}) was running but is now dead")

                self.processes[job_id] = instance

            logger.info(f"Loaded {len(self.processes)} processes from state file")

        except Exception as e:
            logger.error(f"Failed to load state: {e}", exc_info=True)

    def _is_process_alive(self, pid: int) -> bool:
        """Check if process is still alive."""
        try:
            os.kill(pid, 0)  # Doesn't actually kill, just checks if process exists
            return True
        except OSError:
            return False
