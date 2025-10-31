import React, { useState, useEffect } from 'react';
import ScenarioMap from '../components/ScenarioMap';
import ScenarioConfigurator from '../components/ScenarioConfigurator';
import InteractiveScenarioBuilder from '../components/InteractiveScenarioBuilder';
import ScenarioList from '../components/ScenarioList';
import { getScenario, getHospitals, generateScenario } from '../services/api';

export default function ScenarioManager() {
  const [selectedScenarioMeta, setSelectedScenarioMeta] = useState(null);
  const [selectedScenario, setSelectedScenario] = useState(null);
  const [scenarioPreview, setScenarioPreview] = useState(null);
  const [hospitals, setHospitals] = useState([]);
  const [regionBounds, setRegionBounds] = useState(null);
  const [loading, setLoading] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const [currentRegion, setCurrentRegion] = useState('CA');
  const [builderMode, setBuilderMode] = useState('interactive'); // 'interactive' or 'form'

  // Load hospitals for current region
  useEffect(() => {
    loadHospitals(currentRegion);
  }, [currentRegion]);

  // Load full scenario when metadata is selected
  useEffect(() => {
    if (selectedScenarioMeta) {
      loadFullScenario(selectedScenarioMeta.id);

      // Update region if scenario has one
      if (selectedScenarioMeta.region && selectedScenarioMeta.region !== currentRegion) {
        setCurrentRegion(selectedScenarioMeta.region);
      }
    }
  }, [selectedScenarioMeta]);

  const loadHospitals = async (region) => {
    try {
      const response = await getHospitals(region);
      setHospitals(response.data.hospitals);
      setRegionBounds(response.data.bounds);
    } catch (err) {
      console.error('Error loading hospitals:', err);
    }
  };

  const loadFullScenario = async (scenarioId) => {
    try {
      setLoading(true);
      const response = await getScenario(scenarioId);
      setSelectedScenario(response.data.scenario);
      setScenarioPreview(response.data.preview);
    } catch (err) {
      console.error('Error loading scenario:', err);
      alert('Failed to load scenario: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleScenarioGenerated = (data) => {
    setSelectedScenario(data.scenario);
    setScenarioPreview(data.preview);

    // Update region if different
    if (data.scenario.metadata?.region) {
      setCurrentRegion(data.scenario.metadata.region);
    }

    // Refresh scenario list
    setRefreshKey(prev => prev + 1);

    // Show success message
    alert('Scenario generated successfully!');
  };

  const handleInteractiveScenarioCreated = async (scenarioData) => {
    try {
      setLoading(true);
      
      // Call backend to generate scenario with manual placements
      const response = await generateScenario({
        region: scenarioData.region,
        incident_location: scenarioData.incident_location,
        manual_ambulances: scenarioData.manual_ambulances,
        num_casualties: scenarioData.num_casualties,
        name: scenarioData.name,
        save: true,
        // New fields
        ambulances_per_hospital: scenarioData.ambulances_per_hospital,
        ambulances_per_hospital_variation: scenarioData.ambulances_per_hospital_variation,
        casualty_distribution_radius: scenarioData.casualty_radius, // Pass to backend if supported
      });

      handleScenarioGenerated(response.data);
    } catch (err) {
      console.error('Error creating scenario:', err);
      alert('Failed to create scenario: ' + (err.response?.data?.error || err.message));
    } finally {
      setLoading(false);
    }
  };

  const handleSelectScenario = (scenarioMeta) => {
    setSelectedScenarioMeta(scenarioMeta);
  };

  return (
    <div className="h-screen flex flex-col bg-gray-100">
      {/* Top Bar with Mode Toggle */}
      <div className="bg-white border-b border-gray-200 px-4 py-3">
        <div className="flex items-center justify-between">
          <h1 className="text-xl font-bold text-gray-800">Scenario Manager</h1>
          <div className="flex gap-2">
            <button
              onClick={() => setBuilderMode('interactive')}
              className={`px-4 py-2 rounded text-sm font-medium transition ${
                builderMode === 'interactive'
                  ? 'bg-blue-500 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              🗺️ Interactive Builder
            </button>
            <button
              onClick={() => setBuilderMode('form')}
              className={`px-4 py-2 rounded text-sm font-medium transition ${
                builderMode === 'form'
                  ? 'bg-blue-500 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              📋 Form Builder
            </button>
          </div>
        </div>
      </div>

      <div className="flex-1 flex overflow-hidden">
        {/* Conditional Rendering Based on Mode */}
        {builderMode === 'interactive' ? (
          /* Interactive Map-Based Builder */
          <InteractiveScenarioBuilder onScenarioCreated={handleInteractiveScenarioCreated} />
        ) : (
          /* Original Form-Based Builder */
          <>
            <aside className="w-96 bg-gray-50 border-r border-gray-200 overflow-y-auto">
              <div className="p-4 space-y-4">
                <ScenarioConfigurator onScenarioGenerated={handleScenarioGenerated} />
                <ScenarioList
                  selectedScenario={selectedScenario}
                  onSelectScenario={handleSelectScenario}
                  onRefresh={refreshKey}
                />
              </div>
            </aside>

            {/* Main Content - Map & Info */}
            <main className="flex-1 flex flex-col overflow-hidden">
          {/* Info Panel */}
          {scenarioPreview && (
            <div className="bg-white border-b border-gray-200 p-4">
              <div className="flex items-start justify-between">
                <div>
                  <h1 className="text-xl font-bold">
                    {selectedScenario?.metadata?.name || 'Scenario Preview'}
                  </h1>
                  <div className="flex gap-4 mt-2 text-sm text-gray-600">
                    <div>
                      <span className="font-medium">Casualties:</span> {scenarioPreview.num_casualties}
                    </div>
                    <div>
                      <span className="font-medium">Region:</span> {selectedScenario?.metadata?.region || currentRegion}
                    </div>
                    {scenarioPreview.incident_location && (
                      <div>
                        <span className="font-medium">Location:</span>{' '}
                        {scenarioPreview.incident_location[0].toFixed(4)}, {scenarioPreview.incident_location[1].toFixed(4)}
                      </div>
                    )}
                  </div>
                </div>

                <div className="flex gap-2">
                  {selectedScenario?.metadata?.id && (
                    <div className="text-right text-sm">
                      <div className="text-gray-500">Scenario ID</div>
                      <div className="font-mono text-xs">{selectedScenario.metadata.id}</div>
                    </div>
                  )}
                </div>
              </div>

              {/* Triage Breakdown */}
              {scenarioPreview.triage_counts && (
                <div className="mt-4 flex gap-6 text-sm">
                  <div className="flex items-center gap-2">
                    <span className="w-3 h-3 rounded-full bg-red-600"></span>
                    <span className="text-gray-700">
                      Red: <span className="font-semibold">{scenarioPreview.triage_counts.RED || 0}</span>
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="w-3 h-3 rounded-full bg-yellow-400"></span>
                    <span className="text-gray-700">
                      Yellow: <span className="font-semibold">{scenarioPreview.triage_counts.YELLOW || 0}</span>
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="w-3 h-3 rounded-full bg-green-600"></span>
                    <span className="text-gray-700">
                      Green: <span className="font-semibold">{scenarioPreview.triage_counts.GREEN || 0}</span>
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="w-3 h-3 rounded-full bg-gray-700"></span>
                    <span className="text-gray-700">
                      Black: <span className="font-semibold">{scenarioPreview.triage_counts.BLACK || 0}</span>
                    </span>
                  </div>
                </div>
              )}

              {/* Ambulance Configuration */}
              {scenarioPreview.ambulance_config && (
                <div className="mt-3 p-3 bg-blue-50 border border-blue-200 rounded text-sm">
                  <div className="font-semibold text-blue-900 mb-1">Ambulance Configuration:</div>
                  <div className="text-blue-800 space-y-1">
                    <div>
                      🏥 Hospital-based: {scenarioPreview.ambulance_config.ambulances_per_hospital} ±{' '}
                      {scenarioPreview.ambulance_config.ambulances_per_hospital_variation} per hospital
                    </div>
                    <div>
                      🚑 Field units: {scenarioPreview.ambulance_config.field_ambulances} within{' '}
                      {scenarioPreview.ambulance_config.field_ambulance_radius_km} km
                    </div>
                    {scenarioPreview.ambulance_config.seed && (
                      <div className="text-xs text-blue-600">
                        Seed: {scenarioPreview.ambulance_config.seed} (reproducible)
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Map */}
          <div className="flex-1 overflow-hidden">
            {loading ? (
              <div className="h-full flex items-center justify-center bg-gray-100">
                <p className="text-gray-500">Loading scenario...</p>
              </div>
            ) : (
              <ScenarioMap
                preview={scenarioPreview}
                hospitals={hospitals}
                regionBounds={regionBounds}
                showHospitals={true}
              />
            )}
          </div>
            </main>
          </>
        )}
      </div>
    </div>
  );
}
