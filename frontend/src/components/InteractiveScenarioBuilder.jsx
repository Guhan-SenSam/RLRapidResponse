import React, { useState, useEffect, useCallback } from 'react';
import { MapContainer, TileLayer, Marker, useMapEvents, useMap, Circle, Popup } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css'; // Explicit import to ensure styles are loaded
import { getHospitals } from '../services/api';

// Fix for default marker icons
import markerIcon2x from 'leaflet/dist/images/marker-icon-2x.png';
import markerIcon from 'leaflet/dist/images/marker-icon.png';
import markerShadow from 'leaflet/dist/images/marker-shadow.png';

delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconUrl: markerIcon,
  iconRetinaUrl: markerIcon2x,
  shadowUrl: markerShadow,
});

// Custom icons for incident and ambulances
const incidentIcon = new L.Icon({
  iconUrl: 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(`
    <svg xmlns="http://www.w3.org/2000/svg" width="40" height="40" viewBox="0 0 40 40">
      <circle cx="20" cy="20" r="18" fill="#FF4444" stroke="#FFFFFF" stroke-width="3"/>
      <path d="M20 10 L23 24 L17 24 Z" fill="white"/>
      <circle cx="20" cy="28" r="2" fill="white"/>
    </svg>
  `),
  iconSize: [40, 40],
  iconAnchor: [20, 40],
  popupAnchor: [0, -40],
});

const ambulanceIcon = new L.Icon({
  iconUrl: 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(`
    <svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 32 32">
      <circle cx="16" cy="16" r="14" fill="#10B981" stroke="#FFFFFF" stroke-width="3"/>
      <rect x="14" y="10" width="4" height="12" fill="white"/>
      <rect x="10" y="14" width="12" height="4" fill="white"/>
    </svg>
  `),
  iconSize: [32, 32],
  iconAnchor: [16, 32],
  popupAnchor: [0, -32],
});

const hospitalIcon = new L.Icon({
  iconUrl: 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(`
    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 20 20">
      <circle cx="10" cy="10" r="8" fill="#3B82F6" stroke="#FFFFFF" stroke-width="2"/>
      <rect x="8" y="5" width="4" height="10" fill="white"/>
      <rect x="5" y="8" width="10" height="4" fill="white"/>
    </svg>
  `),
  iconSize: [20, 20],
  iconAnchor: [10, 20],
  popupAnchor: [0, -20],
});

// US States list
const US_STATES = [
  { code: 'AL', name: 'Alabama' },
  { code: 'AK', name: 'Alaska' },
  { code: 'AZ', name: 'Arizona' },
  { code: 'AR', name: 'Arkansas' },
  { code: 'CA', name: 'California' },
  { code: 'CO', name: 'Colorado' },
  { code: 'CT', name: 'Connecticut' },
  { code: 'DE', name: 'Delaware' },
  { code: 'FL', name: 'Florida' },
  { code: 'GA', name: 'Georgia' },
  { code: 'HI', name: 'Hawaii' },
  { code: 'ID', name: 'Idaho' },
  { code: 'IL', name: 'Illinois' },
  { code: 'IN', name: 'Indiana' },
  { code: 'IA', name: 'Iowa' },
  { code: 'KS', name: 'Kansas' },
  { code: 'KY', name: 'Kentucky' },
  { code: 'LA', name: 'Louisiana' },
  { code: 'ME', name: 'Maine' },
  { code: 'MD', name: 'Maryland' },
  { code: 'MA', name: 'Massachusetts' },
  { code: 'MI', name: 'Michigan' },
  { code: 'MN', name: 'Minnesota' },
  { code: 'MS', name: 'Mississippi' },
  { code: 'MO', name: 'Missouri' },
  { code: 'MT', name: 'Montana' },
  { code: 'NE', name: 'Nebraska' },
  { code: 'NV', name: 'Nevada' },
  { code: 'NH', name: 'New Hampshire' },
  { code: 'NJ', name: 'New Jersey' },
  { code: 'NM', name: 'New Mexico' },
  { code: 'NY', name: 'New York' },
  { code: 'NC', name: 'North Carolina' },
  { code: 'ND', name: 'North Dakota' },
  { code: 'OH', name: 'Ohio' },
  { code: 'OK', name: 'Oklahoma' },
  { code: 'OR', name: 'Oregon' },
  { code: 'PA', name: 'Pennsylvania' },
  { code: 'RI', name: 'Rhode Island' },
  { code: 'SC', name: 'South Carolina' },
  { code: 'SD', name: 'South Dakota' },
  { code: 'TN', name: 'Tennessee' },
  { code: 'TX', name: 'Texas' },
  { code: 'UT', name: 'Utah' },
  { code: 'VT', name: 'Vermont' },
  { code: 'VA', name: 'Virginia' },
  { code: 'WA', name: 'Washington' },
  { code: 'WV', name: 'West Virginia' },
  { code: 'WI', name: 'Wisconsin' },
  { code: 'WY', name: 'Wyoming' },
];

// Map click handler component
function MapClickHandler({ mode, onIncidentPlace, onAmbulancePlace }) {
  useMapEvents({
    click: (e) => {
      const { lat, lng } = e.latlng;
      if (mode === 'incident') {
        onIncidentPlace([lat, lng]);
      } else if (mode === 'ambulance') {
        onAmbulancePlace([lat, lng]);
      }
    },
  });
  return null;
}

// Auto-fit bounds component
function FitBounds({ bounds }) {
  const map = useMap();
  
  useEffect(() => {
    if (bounds && map) {
      const [[south, west], [north, east]] = [
        [bounds[0], bounds[2]],
        [bounds[1], bounds[3]]
      ];
      map.fitBounds([[south, west], [north, east]], { padding: [50, 50] });
    }
  }, [bounds, map]);
  
  return null;
}

// Component to capture map instance
function MapInstanceCapture({ setMapInstance }) {
  const map = useMap();
  
  useEffect(() => {
    if (map) {
      setMapInstance(map);
    }
  }, [map, setMapInstance]);
  
  return null;
}

export default function InteractiveScenarioBuilder({ onScenarioCreated }) {
  const [selectedState, setSelectedState] = useState('CA');
  const [hospitals, setHospitals] = useState([]);
  const [regionBounds, setRegionBounds] = useState(null);
  const [loading, setLoading] = useState(false);
  
  // Scenario data
  const [incidentLocation, setIncidentLocation] = useState(null);
  const [ambulances, setAmbulances] = useState([]);
  const [casualties, setCasualties] = useState([]);
  
  // UI state
  const [mapMode, setMapMode] = useState('view'); // 'view', 'incident', 'ambulance', 'casualty'
  const [mapInstance, setMapInstance] = useState(null);
  
  // Configuration
  const [config, setConfig] = useState({
    name: '',
    num_casualties: 60,
    casualty_radius: 2.0, // Casualty distribution radius in km
    field_ambulance_radius_km: 10.0,
    ambulances_per_hospital: 2,
    ambulances_per_hospital_variation: 1,
  });

  // Load hospitals when state changes
  useEffect(() => {
    loadHospitals(selectedState);
  }, [selectedState]);

  const loadHospitals = async (state) => {
    try {
      setLoading(true);
      const response = await getHospitals(state);
      setHospitals(response.data.hospitals);
      setRegionBounds(response.data.bounds);
    } catch (err) {
      console.error('Error loading hospitals:', err);
      alert('Failed to load hospitals: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleStateChange = (state) => {
    setSelectedState(state);
    // Reset scenario data when state changes
    setIncidentLocation(null);
    setAmbulances([]);
    setCasualties([]);
  };

  const handleIncidentPlace = (coords) => {
    setIncidentLocation(coords);
    setMapMode('view');
  };

  const handleAmbulancePlace = (coords) => {
    setAmbulances([...ambulances, { lat: coords[0], lon: coords[1], id: ambulances.length }]);
  };

  const removeAmbulance = (index) => {
    setAmbulances(ambulances.filter((_, i) => i !== index));
  };

  const clearAll = () => {
    setIncidentLocation(null);
    setAmbulances([]);
    setCasualties([]);
  };

  const handleGenerate = async () => {
    if (!incidentLocation) {
      alert('Please place an incident location on the map first!');
      return;
    }

    if (ambulances.length === 0) {
      alert('Please place at least one ambulance on the map!');
      return;
    }

    // Create scenario data
    const scenarioData = {
      region: selectedState,
      incident_location: incidentLocation,
      manual_ambulances: ambulances,
      num_casualties: config.num_casualties,
      name: config.name || `${selectedState} Manual Scenario`,
      field_ambulance_radius_km: config.field_ambulance_radius_km,
      // New fields
      casualty_radius: config.casualty_radius,
      ambulances_per_hospital: config.ambulances_per_hospital,
      ambulances_per_hospital_variation: config.ambulances_per_hospital_variation,
    };

    if (onScenarioCreated) {
      onScenarioCreated(scenarioData);
    }
  };

  const getMapCenter = () => {
    if (incidentLocation) return incidentLocation;
    if (regionBounds && regionBounds.length === 4) {
      const [minLat, maxLat, minLon, maxLon] = regionBounds;
      // Ensure we have valid numbers
      if (!isNaN(minLat) && !isNaN(maxLat) && !isNaN(minLon) && !isNaN(maxLon)) {
        return [(minLat + maxLat) / 2, (minLon + maxLon) / 2];
      }
    }
    return [34.0522, -118.2437]; // Default to Los Angeles if bounds fail
  };

  return (
    <div className="h-full flex w-full">
      {/* Sidebar Controls */}
      <div className="w-80 bg-white border-r border-gray-200 overflow-y-auto shadow-lg">
        <div className="p-4 space-y-4">
          <h2 className="text-xl font-bold text-gray-800">Build Scenario</h2>
          
          {/* State Selection */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Select State
            </label>
            <select
              value={selectedState}
              onChange={(e) => handleStateChange(e.target.value)}
              className="w-full border border-gray-300 rounded px-3 py-2 text-sm"
            >
              {US_STATES.map((state) => (
                <option key={state.code} value={state.code}>
                  {state.name}
                </option>
              ))}
            </select>
            {hospitals.length > 0 && (
              <p className="text-xs text-gray-500 mt-1">
                {hospitals.length} hospitals loaded
              </p>
            )}
          </div>

          {/* Scenario Name */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Scenario Name
            </label>
            <input
              type="text"
              value={config.name}
              onChange={(e) => setConfig({ ...config, name: e.target.value })}
              placeholder={`${selectedState} Custom Scenario`}
              className="w-full border border-gray-300 rounded px-3 py-2 text-sm"
            />
          </div>

          {/* Map Mode Selection */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Map Mode
            </label>
            <div className="space-y-2">
              <button
                onClick={() => setMapMode('incident')}
                className={`w-full px-4 py-2 rounded text-sm font-medium transition ${
                  mapMode === 'incident'
                    ? 'bg-red-500 text-white'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                }`}
              >
                {incidentLocation ? '✓ Edit' : '📍 Place'} Incident Location
              </button>
              
              <button
                onClick={() => setMapMode('ambulance')}
                disabled={!incidentLocation}
                className={`w-full px-4 py-2 rounded text-sm font-medium transition ${
                  mapMode === 'ambulance'
                    ? 'bg-green-500 text-white'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200 disabled:bg-gray-50 disabled:text-gray-400'
                }`}
              >
                🚑 Place Ambulances ({ambulances.length})
              </button>

              <button
                onClick={() => setMapMode('view')}
                className={`w-full px-4 py-2 rounded text-sm font-medium transition ${
                  mapMode === 'view'
                    ? 'bg-blue-500 text-white'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                }`}
              >
                👁️ View Only
              </button>
            </div>
          </div>

          {/* Instructions */}
          <div className="bg-blue-50 border border-blue-200 rounded p-3">
            <p className="text-sm text-blue-900 font-medium mb-1">Instructions:</p>
            <ol className="text-xs text-blue-800 space-y-1 list-decimal list-inside">
              <li>Select a state from the dropdown</li>
              <li>Click "Place Incident" and click on the map</li>
              <li>Click "Place Ambulances" and click to add ambulances</li>
              <li>Configure casualties and generate</li>
            </ol>
          </div>

          {/* Placed Items */}
          <div className="space-y-3">
            {/* Incident Info */}
            {incidentLocation && (
              <div className="bg-red-50 border border-red-200 rounded p-3">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-red-900">Incident Location</p>
                    <p className="text-xs text-red-700 font-mono">
                      {incidentLocation[0].toFixed(4)}, {incidentLocation[1].toFixed(4)}
                    </p>
                  </div>
                  <button
                    onClick={() => setIncidentLocation(null)}
                    className="text-red-600 hover:text-red-800 text-xs"
                  >
                    Remove
                  </button>
                </div>
              </div>
            )}

            {/* Ambulances List */}
            {ambulances.length > 0 && (
              <div className="bg-green-50 border border-green-200 rounded p-3">
                <p className="text-sm font-medium text-green-900 mb-2">
                  Ambulances ({ambulances.length})
                </p>
                <div className="space-y-1 max-h-40 overflow-y-auto">
                  {ambulances.map((amb, idx) => (
                    <div key={idx} className="flex items-center justify-between text-xs bg-white rounded px-2 py-1">
                      <span className="font-mono text-green-700">
                        {amb.lat.toFixed(4)}, {amb.lon.toFixed(4)}
                      </span>
                      <button
                        onClick={() => removeAmbulance(idx)}
                        className="text-red-600 hover:text-red-800"
                      >
                        ✕
                      </button>
                    </div>
                  ))}
                </div>
                <button
                  onClick={() => setAmbulances([])}
                  className="w-full mt-2 text-xs text-green-700 hover:text-green-900"
                >
                  Clear All Ambulances
                </button>
              </div>
            )}
          </div>

          {/* Casualties Configuration */}
          <div className="bg-red-50 p-3 rounded border border-red-100">
            <h3 className="text-sm font-bold text-red-900 mb-2">Casualties</h3>
            
            <div className="mb-3">
              <label className="block text-xs font-medium text-gray-700 mb-1">
                Count: {config.num_casualties}
              </label>
              <input
                type="range"
                value={config.num_casualties}
                onChange={(e) => setConfig({ ...config, num_casualties: parseInt(e.target.value) })}
                min="10"
                max="200"
                className="w-full h-2 bg-red-200 rounded-lg appearance-none cursor-pointer"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">
                Spread Radius: {config.casualty_radius} km
              </label>
              <input
                type="range"
                value={config.casualty_radius}
                onChange={(e) => setConfig({ ...config, casualty_radius: parseFloat(e.target.value) })}
                min="0.5"
                max="10.0"
                step="0.5"
                className="w-full h-2 bg-red-200 rounded-lg appearance-none cursor-pointer"
              />
              <p className="text-[10px] text-gray-500 mt-1">
                Area where casualties are scattered
              </p>
            </div>
          </div>

          {/* Ambulance Configuration */}
          <div className="bg-blue-50 p-3 rounded border border-blue-100">
            <h3 className="text-sm font-bold text-blue-900 mb-2">Hospital Ambulances</h3>
            
            <div className="mb-3">
              <label className="block text-xs font-medium text-gray-700 mb-1">
                Base per Hospital: {config.ambulances_per_hospital}
              </label>
              <input
                type="range"
                value={config.ambulances_per_hospital}
                onChange={(e) => setConfig({ ...config, ambulances_per_hospital: parseInt(e.target.value) })}
                min="0"
                max="10"
                className="w-full h-2 bg-blue-200 rounded-lg appearance-none cursor-pointer"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">
                Variation (±): {config.ambulances_per_hospital_variation}
              </label>
              <input
                type="range"
                value={config.ambulances_per_hospital_variation}
                onChange={(e) => setConfig({ ...config, ambulances_per_hospital_variation: parseInt(e.target.value) })}
                min="0"
                max="5"
                className="w-full h-2 bg-blue-200 rounded-lg appearance-none cursor-pointer"
              />
            </div>
          </div>

          {/* Action Buttons */}
          <div className="space-y-2 pt-4 border-t">
            <button
              onClick={handleGenerate}
              disabled={!incidentLocation || ambulances.length === 0}
              className="w-full bg-blue-500 text-white px-4 py-3 rounded hover:bg-blue-600 disabled:bg-gray-300 transition font-medium"
            >
              ✨ Generate Scenario
            </button>
            
            <button
              onClick={clearAll}
              className="w-full bg-gray-200 text-gray-700 px-4 py-2 rounded hover:bg-gray-300 transition text-sm"
            >
              🗑️ Clear All
            </button>
          </div>
        </div>
      </div>

      {/* Map */}
      <div className="flex-1 relative h-full w-full">
        {loading ? (
          <div className="h-full flex items-center justify-center bg-gray-100">
            <p className="text-gray-500">Loading hospitals...</p>
          </div>
        ) : (
          <MapContainer
            center={getMapCenter()}
            zoom={7}
            style={{ height: '100%', width: '100%', minHeight: '500px' }}
            scrollWheelZoom={true}
          >
            <TileLayer
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
            />

            {/* Capture map instance */}
            <MapInstanceCapture setMapInstance={setMapInstance} />

            {/* Auto-fit bounds */}
            {regionBounds && <FitBounds bounds={regionBounds} />}

            {/* Map click handler */}
            <MapClickHandler
              mode={mapMode}
              onIncidentPlace={handleIncidentPlace}
              onAmbulancePlace={handleAmbulancePlace}
            />

            {/* Hospitals */}
            {hospitals.map((hospital, idx) => (
              <Marker
                key={idx}
                position={[hospital.lat, hospital.lon]}
                icon={hospitalIcon}
              >
                <Popup>
                  <div className="text-xs">
                    <strong>{hospital.name}</strong>
                    <div className="mt-1 space-y-0.5">
                      <div>{hospital.city}, {hospital.state}</div>
                      <div>🛏️ {hospital.beds} beds</div>
                      <div>Trauma: {hospital.trauma_level || 'N/A'}</div>
                    </div>
                  </div>
                </Popup>
              </Marker>
            ))}

            {/* Incident Location */}
            {incidentLocation && (
              <>
                <Marker position={incidentLocation} icon={incidentIcon}>
                  <Popup>
                    <div className="text-sm">
                      <strong className="text-red-600">Incident Location</strong>
                      <div className="mt-2 text-xs">
                        <div>📍 {incidentLocation[0].toFixed(6)}, {incidentLocation[1].toFixed(6)}</div>
                        <div className="mt-1">👥 {config.num_casualties} casualties</div>
                      </div>
                    </div>
                  </Popup>
                </Marker>
                
                {/* Field ambulance radius */}
                <Circle
                  center={incidentLocation}
                  radius={config.field_ambulance_radius_km * 1000}
                  pathOptions={{
                    color: '#3B82F6',
                    fillColor: '#3B82F6',
                    fillOpacity: 0.05,
                    weight: 1,
                    dashArray: '5, 10'
                  }}
                />

                {/* Casualty distribution radius */}
                <Circle
                  center={incidentLocation}
                  radius={config.casualty_radius * 1000}
                  pathOptions={{
                    color: '#EF4444',
                    fillColor: '#EF4444',
                    fillOpacity: 0.1,
                    weight: 1,
                  }}
                />
              </>
            )}

            {/* Manually Placed Ambulances */}
            {ambulances.map((amb, idx) => (
              <Marker
                key={idx}
                position={[amb.lat, amb.lon]}
                icon={ambulanceIcon}
              >
                <Popup>
                  <div className="text-sm">
                    <strong className="text-green-600">Ambulance #{idx + 1}</strong>
                    <div className="mt-2 text-xs">
                      <div>📍 {amb.lat.toFixed(6)}, {amb.lon.toFixed(6)}</div>
                      <button
                        onClick={() => removeAmbulance(idx)}
                        className="mt-2 text-red-600 hover:text-red-800 text-xs"
                      >
                        Remove
                      </button>
                    </div>
                  </div>
                </Popup>
              </Marker>
            ))}
          </MapContainer>
        )}

        {/* Mode Indicator */}
        {mapMode !== 'view' && !loading && (
          <div className="absolute top-4 left-1/2 transform -translate-x-1/2 z-[1000] bg-white shadow-lg rounded-lg px-4 py-2 border-2 border-blue-500">
            <p className="text-sm font-medium text-gray-800">
              {mapMode === 'incident' && '📍 Click on the map to place the incident location'}
              {mapMode === 'ambulance' && '🚑 Click on the map to place ambulances'}
            </p>
          </div>
        )}

        {/* Legend */}
        <div className="absolute bottom-4 right-4 bg-white shadow-lg rounded-lg p-3 text-xs z-[1000]">
          <div className="font-semibold mb-2">Legend</div>
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 bg-red-500 rounded-full border-2 border-white"></div>
              <span>Incident</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 bg-green-500 rounded-full border-2 border-white"></div>
              <span>Ambulance</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 bg-blue-500 rounded-full border-2 border-white"></div>
              <span>Hospital</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

