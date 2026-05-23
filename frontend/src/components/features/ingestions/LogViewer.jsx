import React, { useEffect, useState, useRef } from 'react';
import apiClient from '../../../services/api';

export default function LogViewer({ jobId = null, refreshInterval = 3000, isActive = true }) {
    const [logs, setLogs] = useState([]);
    const [error, setError] = useState(null);
    const bottomRef = useRef(null);

    const fetchLogs = async () => {
        if (!jobId) return;

        try {
            // New Endpoint: /jobs/{id}/logs
            const response = await apiClient.get(`/jobs/${jobId}/logs`, {
                params: { limit: 100 }
            });
            // Map DTO to string if needed, or render structured logs
            // DTO: { id, timestamp, log_level, message, step_name }
            setLogs(response.data);
            setError(null);
        } catch (err) {
            console.error("Failed to fetch logs:", err);
            // Don't show error continuously if polling
            // setError("Failed to load logs.");
        }
    };

    useEffect(() => {
        if (jobId && isActive) {
            fetchLogs(); // Initial fetch
            const interval = setInterval(fetchLogs, refreshInterval);
            return () => clearInterval(interval);
        } else if (jobId && !isActive) {
            // Fetch one last time to ensure completed logs are visible
            fetchLogs();
        } else {
            setLogs([]);
        }
    }, [jobId, refreshInterval, isActive]);

    useEffect(() => {
        if (bottomRef.current) {
            bottomRef.current.scrollIntoView({ behavior: "smooth" });
        }
    }, [logs]);

    if (!jobId) {
        return (
            <div className="bg-black rounded-lg font-mono text-xs p-4 h-64 flex items-center justify-center" style={{ border: '1px solid var(--border)', color: 'var(--text-tertiary)' }}>
                Waiting for job to start...
            </div>
        );
    }

    return (
        <div className="bg-black rounded-lg font-mono text-xs p-4 h-64 overflow-y-auto overflow-x-auto custom-scrollbar shadow-inner" style={{ border: '1px solid var(--border)' }}>
            {logs.length === 0 && (
                <div className="italic" style={{ color: 'var(--text-tertiary)' }}>No logs yet...</div>
            )}
            {logs.map((log) => (
                <div key={log.id} className="whitespace-pre pl-2 mb-1 border-l-2 border-transparent min-w-max" style={{ ['--tw-border-opacity']: 1 }}
                    onMouseEnter={(e) => e.currentTarget.style.borderLeftColor = 'var(--border)'}
                    onMouseLeave={(e) => e.currentTarget.style.borderLeftColor = 'transparent'}
                >
                    <span className="mr-2" style={{ color: 'var(--text-tertiary)' }}>[{new Date(log.timestamp).toLocaleTimeString()}]</span>
                    <span style={{ color: log.log_level === 'ERROR' ? 'var(--danger)' : log.log_level === 'WARNING' ? 'var(--warning)' : 'var(--success)' }}>
                        {log.message}
                    </span>
                    {log.step_name && <span className="ml-2 text-[10px] px-1 rounded" style={{ color: 'var(--accent)', background: 'var(--bg-accent-muted)' }}>{log.step_name}</span>}
                </div>
            ))}
            <div ref={bottomRef} />
        </div>
    );
}
