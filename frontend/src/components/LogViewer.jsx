import React, { useEffect, useRef, useState } from 'react';
import { useJobs } from '../contexts/JobContext';
import { getJobLogs, killJob } from '../services/api';

export default function LogViewer() {
  const { selectedJobId, getSelectedJob, getJobLogLines, loadJobs } = useJobs();
  const [autoScroll, setAutoScroll] = useState(true);
  const [killing, setKilling] = useState(false);
  const logEndRef = useRef(null);
  const logContainerRef = useRef(null);

  const job = getSelectedJob();
  const logLines = getJobLogLines(selectedJobId);

  // Auto-scroll to bottom when new logs arrive
  useEffect(() => {
    if (autoScroll && logEndRef.current) {
      logEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logLines, autoScroll]);

  // Load historical logs when job is selected
  useEffect(() => {
    if (!selectedJobId) return;

    const loadHistoricalLogs = async () => {
      try {
        await getJobLogs(selectedJobId, 1000);
        // Note: Historical logs would need to be integrated into context
        // For now, WebSocket provides real-time logs
      } catch (error) {
        console.error('Failed to load logs:', error);
      }
    };

    loadHistoricalLogs();
  }, [selectedJobId]);

  const handleKill = async () => {
    if (!job || !window.confirm('Kill this job?')) return;

    setKilling(true);
    try {
      await killJob(job.id);
      await loadJobs();
    } catch (error) {
      alert('Failed to kill job: ' + error.message);
    } finally {
      setKilling(false);
    }
  };

  if (!job) {
    return (
      <div className="bg-white shadow rounded-lg p-4 h-full flex items-center justify-center">
        <p className="text-gray-500 text-center">
          Select a job to view logs
        </p>
      </div>
    );
  }

  return (
    <div className="bg-white shadow rounded-lg flex flex-col h-full">
      {/* Header */}
      <div className="p-4 border-b border-gray-200">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold">
              {job.process_type} #{job.id.slice(0, 8)}
            </h2>
            <p className="text-sm text-gray-500">
              Status: {job.status} | PID: {job.pid || 'N/A'}
            </p>
          </div>

          <div className="flex items-center space-x-2">
            <label className="flex items-center text-sm">
              <input
                type="checkbox"
                checked={autoScroll}
                onChange={(e) => setAutoScroll(e.target.checked)}
                className="mr-2"
              />
              Auto-scroll
            </label>

            {job.status === 'running' && (
              <button
                onClick={handleKill}
                disabled={killing}
                className="bg-red-500 text-white px-3 py-1 rounded hover:bg-red-600 disabled:bg-gray-300 text-sm transition"
              >
                {killing ? 'Killing...' : 'Kill Job'}
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Log content */}
      <div
        ref={logContainerRef}
        className="flex-1 overflow-y-auto bg-gray-900 text-gray-100 p-4 font-mono text-sm log-viewer"
      >
        {logLines.length === 0 ? (
          <p className="text-gray-500">No logs yet...</p>
        ) : (
          <div className="space-y-1">
            {logLines.map((line, index) => (
              <div key={index} className="whitespace-pre-wrap break-words">
                {line}
              </div>
            ))}
            <div ref={logEndRef} />
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="p-2 border-t border-gray-200 bg-gray-50 text-xs text-gray-600">
        {logLines.length} lines | Log file: {job.log_file}
      </div>
    </div>
  );
}
