import React, { useState } from 'react';
import { generateScenario } from '../services/api';

export default function ScenarioConfigurator({ onScenarioGenerated }) {
  const [config, setConfig] = useState({
    region: 'CA',
    num_casualties: 60,
    ambulances_per_hospital: 2,
    ambulances_per_hospital_variation: 1,
    field_ambulances: 5,
    field_ambulance_radius_km: 10.0,
    seed: '',
    name: '',
    save: true
  });

  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState(null);

  const handleChange = (field, value) => {
    setConfig(prev => ({
      ...prev,
      [field]: value
    }));
  };

  const handleGenerate = async () => {
    setGenerating(true);
    setError(null);

    try {
      // Convert empty string seed to null
      const payload = {
        ...config,
        seed: config.seed === '' ? null : parseInt(config.seed),
        name: config.name === '' ? null : config.name
      };

      const response = await generateScenario(payload);

      if (onScenarioGenerated) {
        onScenarioGenerated(response.data);
      }
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to generate scenario');
    } finally {
      setGenerating(false);
    }
  };

  const handleRandomSeed = () => {
    setConfig(prev => ({
      ...prev,
      seed: Math.floor(Math.random() * 1000000).toString()
    }));
  };

  return (
    <div className="bg-white shadow rounded-lg p-4">
      <h2 className="text-lg font-semibold mb-4">Scenario Configuration</h2>

      <div className="space-y-4">
        {/* Name */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Scenario Name (Optional)
          </label>
          <input
            type="text"
            value={config.name}
            onChange={(e) => handleChange('name', e.target.value)}
            placeholder="e.g., LA Downtown Incident"
            className="w-full border border-gray-300 rounded px-3 py-2 text-sm"
          />
        </div>

        {/* Region */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Region
          </label>
          <select
            value={config.region}
            onChange={(e) => handleChange('region', e.target.value)}
            className="w-full border border-gray-300 rounded px-3 py-2 text-sm"
          >
            <option value="CA">California</option>
            <option value="FL">Florida</option>
            <option value="NY">New York</option>
            <option value="TX">Texas</option>
          </select>
          <p className="text-xs text-gray-500 mt-1">
            Determines which hospitals are available
          </p>
        </div>

        {/* Number of Casualties */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Number of Casualties
          </label>
          <input
            type="number"
            value={config.num_casualties}
            onChange={(e) => handleChange('num_casualties', parseInt(e.target.value))}
            min="10"
            max="200"
            className="w-full border border-gray-300 rounded px-3 py-2 text-sm"
          />
          <input
            type="range"
            value={config.num_casualties}
            onChange={(e) => handleChange('num_casualties', parseInt(e.target.value))}
            min="10"
            max="200"
            className="w-full mt-2"
          />
          <p className="text-xs text-gray-500 mt-1">
            Recommended: 50-80 for training
          </p>
        </div>

        {/* Hospital Ambulances */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Ambulances per Hospital
          </label>
          <div className="flex gap-2">
            <div className="flex-1">
              <input
                type="number"
                value={config.ambulances_per_hospital}
                onChange={(e) => handleChange('ambulances_per_hospital', parseInt(e.target.value))}
                min="0"
                max="10"
                className="w-full border border-gray-300 rounded px-3 py-2 text-sm"
              />
              <p className="text-xs text-gray-500 mt-1">Base count</p>
            </div>
            <div className="flex-1">
              <input
                type="number"
                value={config.ambulances_per_hospital_variation}
                onChange={(e) => handleChange('ambulances_per_hospital_variation', parseInt(e.target.value))}
                min="0"
                max="5"
                className="w-full border border-gray-300 rounded px-3 py-2 text-sm"
              />
              <p className="text-xs text-gray-500 mt-1">± Variation</p>
            </div>
          </div>
          <p className="text-xs text-gray-500 mt-1">
            Each hospital gets {config.ambulances_per_hospital} ± {config.ambulances_per_hospital_variation} ambulances
          </p>
        </div>

        {/* Field Ambulances */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Field Ambulances (First Responders)
          </label>
          <input
            type="number"
            value={config.field_ambulances}
            onChange={(e) => handleChange('field_ambulances', parseInt(e.target.value))}
            min="0"
            max="20"
            className="w-full border border-gray-300 rounded px-3 py-2 text-sm"
          />
          <p className="text-xs text-gray-500 mt-1">
            Units already near the incident scene
          </p>
        </div>

        {/* Field Ambulance Radius */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Field Ambulance Radius (km)
          </label>
          <input
            type="number"
            step="0.5"
            value={config.field_ambulance_radius_km}
            onChange={(e) => handleChange('field_ambulance_radius_km', parseFloat(e.target.value))}
            min="1"
            max="50"
            className="w-full border border-gray-300 rounded px-3 py-2 text-sm"
          />
          <input
            type="range"
            step="0.5"
            value={config.field_ambulance_radius_km}
            onChange={(e) => handleChange('field_ambulance_radius_km', parseFloat(e.target.value))}
            min="1"
            max="50"
            className="w-full mt-2"
          />
          <p className="text-xs text-gray-500 mt-1">
            How far from incident field units spawn
          </p>
        </div>

        {/* Random Seed */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Random Seed (Optional)
          </label>
          <div className="flex gap-2">
            <input
              type="number"
              value={config.seed}
              onChange={(e) => handleChange('seed', e.target.value)}
              placeholder="Auto-generated if empty"
              className="flex-1 border border-gray-300 rounded px-3 py-2 text-sm"
            />
            <button
              type="button"
              onClick={handleRandomSeed}
              className="px-3 py-2 bg-gray-200 text-gray-700 rounded hover:bg-gray-300 text-sm"
            >
              🎲 Random
            </button>
          </div>
          <p className="text-xs text-gray-500 mt-1">
            For reproducible scenarios
          </p>
        </div>

        {/* Save Option */}
        <div className="flex items-center">
          <input
            type="checkbox"
            id="save-scenario"
            checked={config.save}
            onChange={(e) => handleChange('save', e.target.checked)}
            className="mr-2"
          />
          <label htmlFor="save-scenario" className="text-sm text-gray-700">
            Save scenario to disk
          </label>
        </div>

        {/* Error Display */}
        {error && (
          <div className="bg-red-50 text-red-700 p-3 rounded text-sm">
            {error}
          </div>
        )}

        {/* Generate Button */}
        <button
          onClick={handleGenerate}
          disabled={generating}
          className="w-full bg-blue-500 text-white px-4 py-3 rounded hover:bg-blue-600 disabled:bg-gray-300 transition font-medium"
        >
          {generating ? 'Generating...' : '🎲 Generate Scenario'}
        </button>

        {/* Info Box */}
        <div className="bg-blue-50 border border-blue-200 rounded p-3 text-sm">
          <p className="text-blue-800 font-semibold mb-1">Triage Distribution</p>
          <p className="text-blue-700 text-xs">
            Casualties will be automatically distributed:
            <br />• 25% Red (Critical)
            <br />• 40% Yellow (Delayed)
            <br />• 30% Green (Minor)
            <br />• 5% Black (Deceased)
          </p>
        </div>
      </div>
    </div>
  );
}
