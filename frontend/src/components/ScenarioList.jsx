import React, { useState, useEffect } from 'react';
import { listScenarios, deleteScenario } from '../services/api';

export default function ScenarioList({ selectedScenario, onSelectScenario, onRefresh }) {
  const [scenarios, setScenarios] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [deleting, setDeleting] = useState(null);

  useEffect(() => {
    loadScenarios();
  }, [onRefresh]);

  const loadScenarios = async () => {
    try {
      setLoading(true);
      const response = await listScenarios();
      setScenarios(response.data.scenarios);
      setError(null);
    } catch (err) {
      setError('Failed to load scenarios');
      console.error('Error loading scenarios:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (scenarioId, isBenchmark) => {
    if (isBenchmark) {
      alert('Benchmark scenarios cannot be deleted');
      return;
    }

    if (!window.confirm('Delete this scenario?')) {
      return;
    }

    try {
      setDeleting(scenarioId);
      await deleteScenario(scenarioId);
      await loadScenarios();

      // Clear selection if deleted scenario was selected
      if (selectedScenario?.metadata?.id === scenarioId) {
        onSelectScenario(null);
      }
    } catch (err) {
      alert('Failed to delete scenario: ' + err.message);
    } finally {
      setDeleting(null);
    }
  };

  if (loading) {
    return (
      <div className="bg-white shadow rounded-lg p-4">
        <p className="text-gray-500 text-center py-8">Loading scenarios...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-white shadow rounded-lg p-4">
        <p className="text-red-600 text-center py-8">{error}</p>
        <button
          onClick={loadScenarios}
          className="w-full mt-4 px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
        >
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="bg-white shadow rounded-lg p-4">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold">Saved Scenarios ({scenarios.length})</h2>
        <button
          onClick={loadScenarios}
          className="text-sm px-3 py-1 bg-gray-200 rounded hover:bg-gray-300"
        >
          🔄 Refresh
        </button>
      </div>

      {scenarios.length === 0 ? (
        <p className="text-gray-500 text-center py-8">
          No scenarios found. Generate one to get started!
        </p>
      ) : (
        <div className="space-y-2 max-h-96 overflow-y-auto">
          {scenarios.map(scenario => {
            const isSelected = selectedScenario?.metadata?.id === scenario.id;
            const isBenchmark = scenario.is_benchmark;

            return (
              <div
                key={scenario.id}
                className={`p-3 rounded cursor-pointer transition-colors border-2 ${
                  isSelected
                    ? 'border-blue-500 bg-blue-50'
                    : 'border-transparent hover:bg-gray-50'
                }`}
                onClick={() => onSelectScenario(scenario)}
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-sm">
                        {scenario.name || scenario.id}
                      </span>
                      {isBenchmark && (
                        <span className="px-2 py-0.5 bg-purple-100 text-purple-700 text-xs rounded">
                          Benchmark
                        </span>
                      )}
                    </div>

                    <div className="text-xs text-gray-500 mt-1 space-y-0.5">
                      <div>📍 {scenario.region || 'Unknown'}</div>
                      <div>👥 {scenario.configuration?.num_casualties || scenario.num_casualties || 0} casualties</div>
                      {scenario.incident_location && (
                        <div className="text-xs text-gray-400">
                          {scenario.incident_location[0].toFixed(4)}, {scenario.incident_location[1].toFixed(4)}
                        </div>
                      )}
                    </div>

                    {scenario.configuration && (
                      <div className="text-xs text-gray-400 mt-2">
                        🚑 {scenario.configuration.ambulances_per_hospital}±{scenario.configuration.ambulances_per_hospital_variation} per hospital
                        {' + '}
                        {scenario.configuration.field_ambulances} field
                      </div>
                    )}
                  </div>

                  {!isBenchmark && (
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDelete(scenario.id, isBenchmark);
                      }}
                      disabled={deleting === scenario.id}
                      className="ml-2 px-2 py-1 text-red-600 hover:bg-red-50 rounded text-xs"
                    >
                      {deleting === scenario.id ? '...' : '🗑️'}
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
