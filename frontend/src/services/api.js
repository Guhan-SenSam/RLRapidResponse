import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000';

const api = axios.create({
  baseURL: `${API_BASE_URL}/api`,
  headers: {
    'Content-Type': 'application/json',
  },
});

// ============================================================================
// Job Management
// ============================================================================

export const createJob = (type, command, args, autoStart = true) =>
  api.post('/jobs', { type, command, args, auto_start: autoStart });

export const listJobs = (statusFilter = null) => {
  const params = statusFilter ? { status: statusFilter } : {};
  return api.get('/jobs', { params });
};

export const getJob = (jobId) =>
  api.get(`/jobs/${jobId}`);

export const getJobLogs = (jobId, tail = 100) =>
  api.get(`/jobs/${jobId}/logs`, { params: { tail } });

export const startJob = (jobId) =>
  api.post(`/jobs/${jobId}/start`);

export const killJob = (jobId) =>
  api.post(`/jobs/${jobId}/kill`);

// ============================================================================
// Simulations (optional - for live visualization)
// ============================================================================

export const createSimulation = (scenarioConfig, agentType) =>
  api.post('/simulations', { scenario_config: scenarioConfig, agent_type: agentType });

export const listSimulations = () =>
  api.get('/simulations');

export const startSimulation = (simulationId) =>
  api.post(`/simulations/${simulationId}/start`);

export const pauseSimulation = (simulationId) =>
  api.post(`/simulations/${simulationId}/pause`);

export const stopSimulation = (simulationId) =>
  api.post(`/simulations/${simulationId}/stop`);

// ============================================================================
// Scenario Management
// ============================================================================

export const listScenarios = () =>
  api.get('/scenarios');

export const generateScenario = (config) =>
  api.post('/scenarios', config);

export const getScenario = (scenarioId) =>
  api.get(`/scenarios/${scenarioId}`);

export const deleteScenario = (scenarioId) =>
  api.delete(`/scenarios/${scenarioId}`);

export const getHospitals = (region = 'CA') =>
  api.get('/hospitals', { params: { region } });

export default api;
