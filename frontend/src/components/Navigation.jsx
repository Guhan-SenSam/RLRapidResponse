import React from 'react';
import { Link, useLocation } from 'react-router-dom';

export default function Navigation() {
  const location = useLocation();

  const isActive = (path) => location.pathname.startsWith(path);

  return (
    <nav className="bg-blue-600 text-white shadow-lg">
      <div className="container mx-auto px-4">
        <div className="flex items-center justify-between h-16">
          <h1 className="text-xl font-bold">RLRapidResponse</h1>

          <div className="flex space-x-4">
            <Link
              to="/jobs"
              className={`px-4 py-2 rounded transition ${
                isActive('/jobs')
                  ? 'bg-blue-700 font-semibold'
                  : 'hover:bg-blue-500'
              }`}
            >
              Job Dashboard
            </Link>

            <Link
              to="/scenarios"
              className={`px-4 py-2 rounded transition ${
                isActive('/scenarios')
                  ? 'bg-blue-700 font-semibold'
                  : 'hover:bg-blue-500'
              }`}
            >
              Scenarios
            </Link>

            <Link
              to="/visualization"
              className={`px-4 py-2 rounded transition ${
                isActive('/visualization')
                  ? 'bg-blue-700 font-semibold'
                  : 'hover:bg-blue-500'
              }`}
            >
              Live Visualization
            </Link>
          </div>
        </div>
      </div>
    </nav>
  );
}
