import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { useWebSocket } from '../hooks/useWebSocket';
import { listJobs } from '../services/api';

const JobContext = createContext();

export function JobProvider({ children }) {
  const { connected, on } = useWebSocket();
  const [jobs, setJobs] = useState([]);
  const [selectedJobId, setSelectedJobId] = useState(null);
  const [jobLogs, setJobLogs] = useState({});  // jobId -> [log lines]
  const [loading, setLoading] = useState(true);

  // Load jobs on mount
  useEffect(() => {
    loadJobs();
  }, []);

  const loadJobs = async () => {
    try {
      setLoading(true);
      const response = await listJobs();
      setJobs(response.data.jobs);

      // Auto-select first running job, or first job if none running
      if (!selectedJobId && response.data.jobs.length > 0) {
        const runningJob = response.data.jobs.find(j => j.status === 'running');
        setSelectedJobId((runningJob || response.data.jobs[0]).id);
      }
    } catch (error) {
      console.error('Failed to load jobs:', error);
    } finally {
      setLoading(false);
    }
  };

  // Listen to job events
  useEffect(() => {
    if (!connected) return;

    const cleanupStarted = on('job:started', (data) => {
      console.log('Job started:', data);
      loadJobs();
    });

    const cleanupOutput = on('job:output', (data) => {
      setJobLogs(prev => {
        const existing = prev[data.job_id] || [];
        // Keep only last 5000 lines to prevent memory issues
        const newLogs = [...existing, data.line];
        if (newLogs.length > 5000) {
          newLogs.shift();
        }
        return {
          ...prev,
          [data.job_id]: newLogs
        };
      });
    });

    const cleanupCompleted = on('job:completed', (data) => {
      console.log('Job completed:', data);
      loadJobs();
    });

    const cleanupKilled = on('job:killed', (data) => {
      console.log('Job killed:', data);
      loadJobs();
    });

    return () => {
      cleanupStarted?.();
      cleanupOutput?.();
      cleanupCompleted?.();
      cleanupKilled?.();
    };
  }, [connected, on]);

  const getSelectedJob = useCallback(() => {
    return jobs.find(j => j.id === selectedJobId);
  }, [jobs, selectedJobId]);

  const getJobLogLines = useCallback((jobId) => {
    return jobLogs[jobId] || [];
  }, [jobLogs]);

  const clearJobLogs = useCallback((jobId) => {
    setJobLogs(prev => {
      const updated = { ...prev };
      delete updated[jobId];
      return updated;
    });
  }, []);

  const value = {
    jobs,
    selectedJobId,
    setSelectedJobId,
    getSelectedJob,
    getJobLogLines,
    clearJobLogs,
    loadJobs,
    loading,
  };

  return (
    <JobContext.Provider value={value}>
      {children}
    </JobContext.Provider>
  );
}

export const useJobs = () => {
  const context = useContext(JobContext);
  if (!context) {
    throw new Error('useJobs must be used within JobProvider');
  }
  return context;
};
