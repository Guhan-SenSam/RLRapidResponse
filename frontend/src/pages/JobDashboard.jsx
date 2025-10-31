import React from 'react';
import StartJobForm from '../components/StartJobForm';
import JobList from '../components/JobList';
import LogViewer from '../components/LogViewer';

export default function JobDashboard() {
  return (
    <div className="h-screen flex flex-col bg-gray-100">
      <div className="flex-1 flex overflow-hidden">
        {/* Left Sidebar */}
        <aside className="w-96 bg-gray-50 border-r border-gray-200 overflow-y-auto">
          <div className="p-4 space-y-4">
            <StartJobForm />
            <JobList />
          </div>
        </aside>

        {/* Main Content - Log Viewer */}
        <main className="flex-1 p-4 overflow-hidden">
          <LogViewer />
        </main>
      </div>
    </div>
  );
}
