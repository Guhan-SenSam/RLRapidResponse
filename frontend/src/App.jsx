import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { JobProvider } from './contexts/JobContext';
import Navigation from './components/Navigation';
import JobDashboard from './pages/JobDashboard';
import ScenarioManager from './pages/ScenarioManager';
import LiveVisualization from './pages/LiveVisualization';

export default function App() {
  return (
    <Router>
      <JobProvider>
        <div className="min-h-screen bg-gray-100">
          <Navigation />
          <Routes>
            <Route path="/" element={<Navigate to="/jobs" replace />} />
            <Route path="/jobs" element={<JobDashboard />} />
            <Route path="/scenarios" element={<ScenarioManager />} />
            <Route path="/visualization" element={<LiveVisualization />} />
          </Routes>
        </div>
      </JobProvider>
    </Router>
  );
}
