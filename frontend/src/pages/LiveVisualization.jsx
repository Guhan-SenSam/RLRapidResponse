import React from 'react';

export default function LiveVisualization() {
  return (
    <div className="h-screen flex items-center justify-center bg-gray-100">
      <div className="bg-white shadow-lg rounded-lg p-8 max-w-2xl">
        <h1 className="text-3xl font-bold text-gray-800 mb-4">
          Live Simulation Visualization
        </h1>
        <p className="text-gray-600 mb-6">
          This feature will display real-time interactive simulations with map visualization,
          ambulance tracking, and casualty status updates.
        </p>
        <div className="bg-blue-50 border border-blue-200 rounded p-4">
          <h2 className="text-lg font-semibold text-blue-800 mb-2">Coming Soon</h2>
          <ul className="text-sm text-blue-700 space-y-1">
            <li>• Interactive map with ambulances and casualties</li>
            <li>• Real-time metrics dashboard</li>
            <li>• Simulation playback controls (start/pause/speed)</li>
            <li>• Multiple concurrent simulation support</li>
          </ul>
        </div>
        <div className="mt-6 text-sm text-gray-500">
          <p>
            For now, use the <strong>Job Dashboard</strong> to start and monitor
            training/evaluation jobs.
          </p>
        </div>
      </div>
    </div>
  );
}
