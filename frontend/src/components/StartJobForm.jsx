import React, { useState, useEffect } from 'react';
import { createJob, listScenarios } from '../services/api';
import { useJobs } from '../contexts/JobContext';

export default function StartJobForm() {
  const { loadJobs } = useJobs();
  const [jobType, setJobType] = useState('training');
  const [timesteps, setTimesteps] = useState('100000');
  const [selectedScenario, setSelectedScenario] = useState('');
  const [scenarios, setScenarios] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    loadScenariosList();
  }, []);

  const loadScenariosList = async () => {
    try {
      const response = await listScenarios();
      setScenarios(response.data.scenarios);
    } catch (err) {
      console.error('Error loading scenarios:', err);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      let args;
      if (jobType === 'training') {
        args = [
          'simulator/train.py',
          '--timesteps', timesteps,
          '--output', `models/ppo_${Date.now()}.zip`
        ];
      } else {
        args = [
          'simulator/evaluate.py',
          '--model', 'models/ppo_mci.zip',
          '--num-scenarios', '100'
        ];
      }

      await createJob(jobType, '.venv/bin/python', args, true);
      await loadJobs();

      // Reset form
      setTimesteps('100000');
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to start job');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-white shadow rounded-lg p-4">
      <h2 className="text-lg font-semibold mb-4">Start New Job</h2>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Job Type
          </label>
          <select
            value={jobType}
            onChange={(e) => setJobType(e.target.value)}
            className="w-full border border-gray-300 rounded px-3 py-2"
          >
            <option value="training">Training</option>
            <option value="evaluation">Evaluation</option>
          </select>
        </div>

        {jobType === 'training' && (
          <>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Timesteps
              </label>
              <input
                type="number"
                value={timesteps}
                onChange={(e) => setTimesteps(e.target.value)}
                className="w-full border border-gray-300 rounded px-3 py-2"
                min="1000"
                step="1000"
              />
              <p className="text-xs text-gray-500 mt-1">
                Recommended: 100k-1M for training
              </p>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Scenario (Optional)
              </label>
              <select
                value={selectedScenario}
                onChange={(e) => setSelectedScenario(e.target.value)}
                className="w-full border border-gray-300 rounded px-3 py-2"
              >
                <option value="">Random scenarios</option>
                {scenarios.map(scenario => (
                  <option key={scenario.id} value={scenario.id}>
                    {scenario.name || scenario.id} ({scenario.configuration?.num_casualties || '?'} casualties)
                  </option>
                ))}
              </select>
              <p className="text-xs text-gray-500 mt-1">
                Leave empty for random generation, or select a specific scenario
              </p>
            </div>
          </>
        )}

        {error && (
          <div className="bg-red-50 text-red-700 p-3 rounded text-sm">
            {error}
          </div>
        )}

        <button
          type="submit"
          disabled={loading}
          className="w-full bg-green-500 text-white px-4 py-2 rounded hover:bg-green-600 disabled:bg-gray-300 transition"
        >
          {loading ? 'Starting...' : `Start ${jobType}`}
        </button>
      </form>
    </div>
  );
}
