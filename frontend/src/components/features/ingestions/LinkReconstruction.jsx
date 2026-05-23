import React, { useState, useEffect } from 'react';
import { FaLink, FaCogs, FaPlay, FaCheckCircle, FaExclamationCircle } from 'react-icons/fa';
import apiClient from '../../../services/api';
import { GenericIngestionLayout } from './IngestionComponents';

const LinkReconstruction = () => {
    // --- Configuration State ---
    const [config, setConfig] = useState({ interval_minutes: 15 });
    const [configLoading, setConfigLoading] = useState(false);
    const [message, setMessage] = useState(null);
    const [configError, setConfigError] = useState(null);

    // --- Jobs State ---
    const [currentJobId, setCurrentJobId] = useState(null);

    // --- Trigger State ---
    const [triggerLoading, setTriggerLoading] = useState(false);
    const [triggerResult, setTriggerResult] = useState(null);

    const endpoints = {
        jobs: "/jobs/?ingestion_type=link_reconstruction",
        progress: "/jobs",
        logs: "/jobs",
    };

    // --- Configuration Logic ---
    useEffect(() => {
        fetchConfig();
    }, []);

    const fetchConfig = async () => {
        try {
            const response = await apiClient.get('/admin/settings');
            const settings = response.data || [];
            const intervalSetting = settings.find(s => s.key === "LINK_RECONSTRUCTION_INTERVAL_MINUTES");
            if (intervalSetting) {
                setConfig({ interval_minutes: parseInt(intervalSetting.value) });
            } else {
                setConfig({ interval_minutes: 15 });
            }
        } catch (err) {
            console.error("Failed to fetch config", err);
        }
    };

    const handleSaveConfig = async (e) => {
        e.preventDefault();
        setConfigLoading(true);
        setMessage(null);
        setConfigError(null);
        try {
            await apiClient.post('/admin/settings', {
                key: "LINK_RECONSTRUCTION_INTERVAL_MINUTES",
                value: config.interval_minutes.toString(),
                description: "Interval in minutes for link reconstruction job"
            });
            setMessage("Configuration saved successfully.");
            setTimeout(() => setMessage(null), 3000);
        } catch (err) {
            setConfigError("Failed to save configuration.");
            console.error(err);
        } finally {
            setConfigLoading(false);
        }
    };

    // --- Action Logic ---
    const handleRunNow = async () => {
        setTriggerLoading(true);
        setTriggerResult(null);
        try {
            const { data } = await apiClient.post('/ingest/reconstruct-links');
            if (data.job_id) {
                setCurrentJobId(data.job_id);
                // The GenericIngestionLayout's polling will pick it up
            } else {
                setTriggerResult({ type: 'success', message: `Task started: ${data.task_id}` });
            }
        } catch (err) {
            setTriggerResult({ type: 'error', message: err.response?.data?.detail || "Failed to trigger task" });
        } finally {
            setTriggerLoading(false);
        }
    };

    return (
        <GenericIngestionLayout
            endpoints={endpoints}
            currentJobId={currentJobId}
            onSelectJob={setCurrentJobId}
            onJobStarted={setCurrentJobId}
        >
            <div className="h-full flex flex-col p-4 md:p-6 animate-fade-in overflow-y-auto">
                <div className="max-w-3xl mx-auto w-full">
                    <h2 className="text-lg md:text-2xl font-bold mb-4 md:mb-6 flex items-center gap-2" style={{ color: 'var(--text-primary)' }}>
                        <FaLink style={{ color: 'var(--accent)' }} /> Link Reconstruction
                    </h2>

                    {/* Configuration Panel */}
                    <div className="glass-panel rounded-xl p-4 md:p-6 mb-6 md:mb-8 shadow-lg" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
                        <h3 className="text-lg font-bold mb-4 flex items-center gap-2" style={{ color: 'var(--text-primary)' }}>
                            <FaCogs style={{ color: 'var(--text-secondary)' }} /> Configuration
                        </h3>

                        <div className="flex flex-col md:flex-row md:items-end gap-3 mb-4">
                            <div className="flex-1">
                                <label className="si-label block mb-1">
                                    Run Interval (Minutes)
                                </label>
                                <input
                                    type="number"
                                    min="1"
                                    value={config.interval_minutes}
                                    onChange={(e) => setConfig({ ...config, interval_minutes: parseInt(e.target.value) || 15 })}
                                    className="si-input w-full"
                                />
                            </div>
                            <button
                                onClick={handleSaveConfig}
                                disabled={configLoading}
                                className="si-button-secondary px-6 py-2 rounded font-bold transition-colors"
                            >
                                {configLoading ? "Saving..." : "Save Config"}
                            </button>
                        </div>
                        {message && (
                            <div className="text-xs p-2 rounded" style={message.includes('success') ? { background: 'var(--success-bg)', color: 'var(--success)' } : { background: 'var(--danger-bg)', color: 'var(--danger)' }}>
                                {message}
                            </div>
                        )}
                        {configError && (
                            <div className="text-xs p-2 rounded" style={{ background: 'var(--danger-bg)', color: 'var(--danger)' }}>{configError}</div>
                        )}
                    </div>

                    {/* Manual Trigger Panel */}
                    <div className="glass-panel rounded-xl p-4 md:p-6 shadow-lg relative overflow-hidden group" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
                        <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity hidden md:block">
                            <FaPlay className="text-9xl" style={{ color: 'var(--accent)' }} />
                        </div>

                        <h3 className="text-base md:text-lg font-bold mb-4 flex items-center gap-2 relative z-10" style={{ color: 'var(--text-primary)' }}>
                            <FaPlay style={{ color: 'var(--accent)' }} /> Manual Trigger
                        </h3>

                        <p className="text-sm mb-6 relative z-10 max-w-lg" style={{ color: 'var(--text-secondary)' }}>
                            Manually trigger the link reconstruction process. This will scan for groups with missing links and valid keys, regenerate the links, and update the search index.
                        </p>

                        <button
                            onClick={handleRunNow}
                            disabled={triggerLoading}
                            className={`relative z-10 flex items-center gap-2 px-6 py-3 rounded-lg font-bold text-sm transition-all ${triggerLoading
                                ? 'cursor-not-allowed'
                                : 'shadow-lg'
                                }`}
                            style={triggerLoading
                                ? { background: 'var(--bg-hover)', color: 'var(--text-secondary)' }
                                : { background: 'var(--success)', color: 'var(--text-primary)' }}
                        >
                            {triggerLoading ? (
                                <>Starting...</>
                            ) : (
                                <>Run Reconstruction Now</>
                            )}
                        </button>

                        {triggerResult && (
                            <div className="mt-4 p-3 rounded relative z-10 text-xs font-mono flex items-center gap-2"
                                style={triggerResult.type === 'success'
                                    ? { background: 'var(--success-bg)', border: '1px solid var(--success)', color: 'var(--success)' }
                                    : { background: 'var(--danger-bg)', border: '1px solid var(--danger)', color: 'var(--danger)' }}>
                                {triggerResult.type === 'success' ? <FaCheckCircle /> : <FaExclamationCircle />}
                                {triggerResult.message}
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </GenericIngestionLayout>
    );
};

export default LinkReconstruction;
