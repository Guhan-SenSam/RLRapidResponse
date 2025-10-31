import React, { useState } from 'react';
import { useJobs } from '../contexts/JobContext';

export default function JobList() {
  const { jobs, selectedJobId, setSelectedJobId, loading } = useJobs();
  const [filterStatus, setFilterStatus] = useState('all');

  const filteredJobs = filterStatus === 'all'
    ? jobs
    : jobs.filter(j => j.status === filterStatus);

  const getStatusColor = (status) => {
    const colors = {
      running: 'bg-green-500',
      completed: 'bg-blue-500',
      failed: 'bg-red-500',
      killed: 'bg-gray-500',
      created: 'bg-yellow-500',
    };
    return colors[status] || 'bg-gray-400';
  };

  const getTypeIcon = (type) => {
    const icons = {
      training: '🎓',
      evaluation: '📊',
      simulation: '🎮',
    };
    return icons[type] || '📄';
  };

  if (loading) {
    return (
      <div className="bg-white shadow rounded-lg p-4">
        <p className="text-gray-500 text-center py-8">Loading jobs...</p>
      </div>
    );
  }

  return (
    <div className="bg-white shadow rounded-lg p-4">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold">Jobs ({filteredJobs.length})</h2>

        <select
          value={filterStatus}
          onChange={(e) => setFilterStatus(e.target.value)}
          className="border border-gray-300 rounded px-3 py-1 text-sm"
        >
          <option value="all">All</option>
          <option value="running">Running</option>
          <option value="completed">Completed</option>
          <option value="failed">Failed</option>
        </select>
      </div>

      {filteredJobs.length === 0 ? (
        <p className="text-gray-500 text-center py-8">No jobs found</p>
      ) : (
        <div className="space-y-2 max-h-96 overflow-y-auto">
          {filteredJobs.map(job => (
            <div
              key={job.id}
              onClick={() => setSelectedJobId(job.id)}
              className={`p-3 rounded cursor-pointer transition-colors border-2 ${
                selectedJobId === job.id
                  ? 'border-blue-500 bg-blue-50'
                  : 'border-transparent hover:bg-gray-50'
              }`}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-3">
                  <span className="text-2xl">{getTypeIcon(job.process_type)}</span>
                  <div>
                    <div className="font-medium text-sm">
                      {job.process_type} #{job.id.slice(0, 8)}
                    </div>
                    <div className="text-xs text-gray-500">
                      {new Date(job.created_at).toLocaleString()}
                    </div>
                  </div>
                </div>

                <div className="flex items-center space-x-2">
                  <div className={`w-3 h-3 rounded-full ${getStatusColor(job.status)}`} />
                  <span className="text-xs text-gray-600">{job.status}</span>
                </div>
              </div>

              {job.pid && (
                <div className="text-xs text-gray-500 mt-1">
                  PID: {job.pid}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
