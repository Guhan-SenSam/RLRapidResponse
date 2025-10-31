import React, { useEffect } from 'react';
import { MapContainer, TileLayer, Marker, Popup, Circle, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

// Fix for default marker icons in Leaflet with Vite
import markerIcon2x from 'leaflet/dist/images/marker-icon-2x.png';
import markerIcon from 'leaflet/dist/images/marker-icon.png';
import markerShadow from 'leaflet/dist/images/marker-shadow.png';

delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconUrl: markerIcon,
  iconRetinaUrl: markerIcon2x,
  shadowUrl: markerShadow,
});

// Custom icons (using proper SVG shapes instead of emojis to avoid btoa() Unicode issues)
const incidentIcon = new L.Icon({
  iconUrl: 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(`
    <svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 32 32">
      <circle cx="16" cy="16" r="14" fill="#FF4444" stroke="#FFFFFF" stroke-width="3"/>
      <path d="M16 8 L18 18 L14 18 Z" fill="white"/>
      <circle cx="16" cy="21" r="1.5" fill="white"/>
    </svg>
  `),
  iconSize: [32, 32],
  iconAnchor: [16, 32],
  popupAnchor: [0, -32],
});

const hospitalIcon = new L.Icon({
  iconUrl: 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(`
    <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24">
      <circle cx="12" cy="12" r="10" fill="#3B82F6" stroke="#FFFFFF" stroke-width="2"/>
      <rect x="10" y="7" width="4" height="10" fill="white"/>
      <rect x="7" y="10" width="10" height="4" fill="white"/>
    </svg>
  `),
  iconSize: [24, 24],
  iconAnchor: [12, 24],
  popupAnchor: [0, -24],
});

// Triage color icons (using encodeURIComponent instead of btoa to avoid Unicode issues)
const triageIcons = {
  RED: new L.Icon({
    iconUrl: 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(`
      <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16">
        <circle cx="8" cy="8" r="7" fill="#DC2626" stroke="#FFFFFF" stroke-width="2"/>
      </svg>
    `),
    iconSize: [16, 16],
    iconAnchor: [8, 8],
  }),
  YELLOW: new L.Icon({
    iconUrl: 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(`
      <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16">
        <circle cx="8" cy="8" r="7" fill="#FBBF24" stroke="#FFFFFF" stroke-width="2"/>
      </svg>
    `),
    iconSize: [16, 16],
    iconAnchor: [8, 8],
  }),
  GREEN: new L.Icon({
    iconUrl: 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(`
      <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16">
        <circle cx="8" cy="8" r="7" fill="#10B981" stroke="#FFFFFF" stroke-width="2"/>
      </svg>
    `),
    iconSize: [16, 16],
    iconAnchor: [8, 8],
  }),
  BLACK: new L.Icon({
    iconUrl: 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(`
      <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16">
        <circle cx="8" cy="8" r="7" fill="#1F2937" stroke="#FFFFFF" stroke-width="2"/>
      </svg>
    `),
    iconSize: [16, 16],
    iconAnchor: [8, 8],
  }),
};

// Component to auto-fit bounds
function FitBounds({ bounds }) {
  const map = useMap();

  useEffect(() => {
    if (bounds && bounds.length === 4) {
      const [[south, west], [north, east]] = [
        [bounds[0], bounds[2]],
        [bounds[1], bounds[3]]
      ];
      map.fitBounds([[south, west], [north, east]], { padding: [50, 50] });
    }
  }, [map, bounds]);

  return null;
}

export default function ScenarioMap({ preview, hospitals, regionBounds, showHospitals = true }) {
  if (!preview) {
    return (
      <div className="h-full bg-gray-100 flex items-center justify-center">
        <p className="text-gray-500">No scenario selected</p>
      </div>
    );
  }

  const { incident_location, casualties = [], ambulance_config, triage_counts } = preview;

  // Calculate map center
  const center = incident_location || [34.05, -118.25];

  return (
    <div className="h-full relative">
      <MapContainer
        center={center}
        zoom={10}
        className="h-full w-full"
        scrollWheelZoom={true}
      >
        <TileLayer
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        />

        {/* Auto-fit bounds */}
        {regionBounds && <FitBounds bounds={regionBounds} />}

        {/* Incident Location */}
        {incident_location && (
          <Marker position={incident_location} icon={incidentIcon}>
            <Popup>
              <div className="text-sm">
                <strong className="text-red-600">Incident Location</strong>
                <div className="mt-2 space-y-1">
                  <div>📍 {incident_location[0].toFixed(6)}, {incident_location[1].toFixed(6)}</div>
                  <div>👥 {casualties.length} casualties</div>
                  {triage_counts && (
                    <div className="mt-2">
                      <div className="font-semibold">Triage:</div>
                      <div className="pl-2">
                        <div>🔴 Red: {triage_counts.RED || 0}</div>
                        <div>🟡 Yellow: {triage_counts.YELLOW || 0}</div>
                        <div>🟢 Green: {triage_counts.GREEN || 0}</div>
                        <div>⚫ Black: {triage_counts.BLACK || 0}</div>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </Popup>
          </Marker>
        )}

        {/* Field Ambulance Radius */}
        {incident_location && ambulance_config && (
          <Circle
            center={incident_location}
            radius={ambulance_config.field_ambulance_radius_km * 1000}
            pathOptions={{
              color: '#3B82F6',
              fillColor: '#3B82F6',
              fillOpacity: 0.1,
              weight: 2,
              dashArray: '5, 10'
            }}
          >
            <Popup>
              <div className="text-sm">
                <strong>Field Ambulance Zone</strong>
                <div className="mt-2">
                  {ambulance_config.field_ambulances} field units will spawn within {ambulance_config.field_ambulance_radius_km} km
                </div>
              </div>
            </Popup>
          </Circle>
        )}

        {/* Casualties */}
        {casualties.map((casualty, idx) => (
          <Marker
            key={idx}
            position={[casualty.lat, casualty.lon]}
            icon={triageIcons[casualty.triage] || triageIcons.GREEN}
          >
            <Popup>
              <div className="text-sm">
                <strong>Casualty #{casualty.id}</strong>
                <div>Triage: <span className={`font-bold ${
                  casualty.triage === 'RED' ? 'text-red-600' :
                  casualty.triage === 'YELLOW' ? 'text-yellow-600' :
                  casualty.triage === 'GREEN' ? 'text-green-600' :
                  'text-gray-600'
                }`}>{casualty.triage}</span></div>
              </div>
            </Popup>
          </Marker>
        ))}

        {/* Hospitals */}
        {showHospitals && hospitals && hospitals.map((hospital, idx) => (
          <Marker
            key={idx}
            position={[hospital.lat, hospital.lon]}
            icon={hospitalIcon}
          >
            <Popup>
              <div className="text-sm">
                <strong>{hospital.name}</strong>
                <div className="mt-2 space-y-1">
                  <div>📍 {hospital.city}, {hospital.state}</div>
                  <div>🛏️ {hospital.beds} beds</div>
                  <div>🏥 Trauma Level: {hospital.trauma_level || 'N/A'}</div>
                  <div>🚁 Helipad: {hospital.helipad ? 'Yes' : 'No'}</div>
                  {ambulance_config && (
                    <div className="mt-2 pt-2 border-t">
                      <div className="font-semibold">Ambulances:</div>
                      <div>{ambulance_config.ambulances_per_hospital} ± {ambulance_config.ambulances_per_hospital_variation}</div>
                    </div>
                  )}
                </div>
              </div>
            </Popup>
          </Marker>
        ))}
      </MapContainer>

      {/* Legend */}
      <div className="absolute bottom-4 right-4 bg-white shadow-lg rounded-lg p-3 text-xs z-[1000]">
        <div className="font-semibold mb-2">Legend</div>
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <span className="text-lg">⚠️</span>
            <span>Incident</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-lg">🏥</span>
            <span>Hospital</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="inline-block w-3 h-3 rounded-full bg-red-600"></span>
            <span>Red (Critical)</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="inline-block w-3 h-3 rounded-full bg-yellow-400"></span>
            <span>Yellow (Delayed)</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="inline-block w-3 h-3 rounded-full bg-green-600"></span>
            <span>Green (Minor)</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="inline-block w-3 h-3 rounded-full bg-gray-700"></span>
            <span>Black (Deceased)</span>
          </div>
        </div>
      </div>
    </div>
  );
}
