import React, { useState, useEffect } from 'react';
import { FaSyncAlt, FaCogs, FaPlay, FaCheckCircle, FaExclamationCircle, FaClock, FaNetworkWired, FaShieldAlt, FaSlidersH } from 'react-icons/fa';
import { PiFloppyDiskBold } from 'react-icons/pi';
import apiClient from '../../../services/api';
import { GenericIngestionLayout } from './IngestionComponents';

// Setting definitions grouped by category
const SETTING_GROUPS = [
    {
        label: "Schedule",
        icon: <FaClock style={{ color: 'var(--accent)' }} />,
        settings: [
            { key: "AVATAR_SYNC_ENABLED", label: "Scheduled Sync", type: "toggle", default: "false", description: "Run avatar sync automatically on schedule" },
            { key: "AVATAR_SYNC_INTERVAL_HOURS", label: "Run Interval (Hours)", type: "number", default: "24", min: 1, max: 720, description: "Hours between scheduled runs" },
        ],
    },
    {
        label: "Smart Filtering",
        icon: <FaSlidersH style={{ color: 'var(--warning)' }} />,
        settings: [
            { key: "AVATAR_SYNC_CHECK_HIGH_FREQ_HOURS", label: "HIGH Tier (Hours)", type: "number", default: "6", min: 1, max: 168, description: "Re-check frequently changing avatars" },
            { key: "AVATAR_SYNC_CHECK_MEDIUM_FREQ_HOURS", label: "MEDIUM Tier (Hours)", type: "number", default: "72", min: 1, max: 720, description: "Re-check moderately changing avatars" },
            { key: "AVATAR_SYNC_CHECK_LOW_FREQ_HOURS", label: "LOW Tier (Hours)", type: "number", default: "168", min: 1, max: 2160, description: "Re-check stable avatars" },
            { key: "AVATAR_SYNC_CHECK_NEVER_VERIFIED_HOURS", label: "Never Verified (Hours)", type: "number", default: "24", min: 1, max: 168, description: "Check new/unverified avatars within this window" },
        ],
    },
    {
        label: "Performance",
        icon: <FaNetworkWired style={{ color: 'var(--success)' }} />,
        settings: [
            { key: "AVATAR_SYNC_BATCH_SIZE", label: "Batch Size", type: "number", default: "100", min: 10, max: 1000, description: "Users processed per batch" },
            { key: "AVATAR_SYNC_CDN_REQUESTS_PER_SEC", label: "CDN Rate Limit (req/s)", type: "number", default: "10", min: 1, max: 100, description: "Max CDN requests per second" },
            { key: "AVATAR_SYNC_THREAD_POOL_SIZE", label: "Thread Pool Size", type: "number", default: "16", min: 1, max: 64, description: "Concurrent CDN fetch threads per batch" },
            { key: "AVATAR_SYNC_SHARD_COUNT", label: "Shard Count", type: "number", default: "4", min: 1, max: 16, description: "Parallel worker shards" },
            { key: "AVATAR_SYNC_BATCH_DELAY_SECONDS", label: "Batch Delay (Seconds)", type: "number", default: "2", min: 0, max: 30, description: "Delay between batches for queue fairness" },
        ],
    },
    {
        label: "Safety",
        icon: <FaShieldAlt style={{ color: 'var(--danger)' }} />,
        settings: [
            { key: "AVATAR_SYNC_CDN_TIMEOUT", label: "CDN Timeout (Seconds)", type: "number", default: "15", min: 5, max: 60, description: "HTTP request timeout for CDN" },
            { key: "AVATAR_SYNC_TIMEOUT_SECONDS", label: "Job Timeout (Seconds)", type: "number", default: "3600", min: 300, max: 14400, description: "Hard limit before job is killed" },
            { key: "AVATAR_SYNC_SSIM_THRESHOLD", label: "SSIM Threshold", type: "decimal", default: "0.9", min: 0.5, max: 1.0, step: 0.05, description: "Visual similarity threshold (0.9 = 90% similar = same)" },
            { key: "AVATAR_SYNC_MAX_RETRIES", label: "Max Retries", type: "number", default: "2", min: 0, max: 5, description: "Per-batch Celery retry limit" },
        ],
    },
];

// Flatten all setting keys for easy lookup
const ALL_SETTING_KEYS = SETTING_GROUPS.flatMap(g => g.settings.map(s => s.key));

const AvatarSync = () => {
    const [settings, setSettings] = useState({});
    const [savedSettings, setSavedSettings] = useState({});
    const [configLoading, setConfigLoading] = useState(false);
    const [message, setMessage] = useState(null);
    const [configError, setConfigError] = useState(null);
    const [expandedGroup, setExpandedGroup] = useState(null);

    const [currentJobId, setCurrentJobId] = useState(null);
    const [triggerLoading, setTriggerLoading] = useState(false);
    const [triggerResult, setTriggerResult] = useState(null);

    const endpoints = {
        jobs: "/jobs/?ingestion_type=avatar_sync",
        progress: "/jobs",
        logs: "/jobs",
    };

    useEffect(() => {
        fetchConfig();
    }, []);

    const fetchConfig = async () => {
        try {
            const response = await apiClient.get('/admin/settings');
            const serverSettings = response.data || [];
            const mapped = {};
            for (const s of serverSettings) {
                if (ALL_SETTING_KEYS.includes(s.key)) {
                    mapped[s.key] = s.value;
                }
            }
            // Fill defaults for any missing keys
            for (const group of SETTING_GROUPS) {
                for (const def of group.settings) {
                    if (!(def.key in mapped)) {
                        mapped[def.key] = def.default;
                    }
                }
            }
            setSettings(mapped);
            setSavedSettings({ ...mapped });
        } catch (err) {
            console.error("Failed to fetch avatar sync config", err);
        }
    };

    const hasChanges = JSON.stringify(settings) !== JSON.stringify(savedSettings);

    const handleSaveConfig = async (e) => {
        e.preventDefault();
        setConfigLoading(true);
        setMessage(null);
        setConfigError(null);
        try {
            // Only save changed keys
            const promises = [];
            for (const group of SETTING_GROUPS) {
                for (const def of group.settings) {
                    if (settings[def.key] !== savedSettings[def.key]) {
                        promises.push(
                            apiClient.post('/admin/settings', {
                                key: def.key,
                                value: String(settings[def.key]),
                                description: def.description,
                            })
                        );
                    }
                }
            }
            await Promise.all(promises);
            setSavedSettings({ ...settings });
            setMessage(`${promises.length} setting${promises.length !== 1 ? 's' : ''} saved successfully.`);
            setTimeout(() => setMessage(null), 3000);
        } catch (err) {
            setConfigError("Failed to save configuration.");
            console.error(err);
        } finally {
            setConfigLoading(false);
        }
    };

    const handleRunNow = async () => {
        setTriggerLoading(true);
        setTriggerResult(null);
        try {
            const { data } = await apiClient.post('/ingest/avatar-sync');
            if (data.job_id) {
                setCurrentJobId(data.job_id);
                setTriggerResult({ type: 'success', message: `Sync started (Job #${data.job_id})` });
            } else {
                setTriggerResult({ type: 'success', message: `Task started: ${data.task_id}` });
            }
        } catch (err) {
            const detail = err.response?.data?.detail || "Failed to trigger avatar sync";
            setTriggerResult({ type: 'error', message: detail });
        } finally {
            setTriggerLoading(false);
        }
    };

    const updateSetting = (key, value) => {
        setSettings(prev => ({ ...prev, [key]: value }));
    };

    const renderSettingInput = (def) => {
        const value = settings[def.key];

        if (def.type === "toggle") {
            const isOn = value === "true" || value === true;
            return (
                <button
                    onClick={() => updateSetting(def.key, isOn ? "false" : "true")}
                    className={`w-full px-3 py-2 rounded font-bold text-xs transition-colors`}
                    style={isOn
                        ? { background: 'var(--success-bg)', border: '1px solid var(--success)', color: 'var(--success)' }
                        : { background: 'var(--bg-hover)', border: '1px solid var(--border)', color: 'var(--text-tertiary)' }}
                >
                    {isOn ? 'Enabled' : 'Disabled'}
                </button>
            );
        }

        if (def.type === "decimal") {
            return (
                <input
                    type="number"
                    min={def.min}
                    max={def.max}
                    step={def.step || 0.05}
                    value={value || def.default}
                    onChange={(e) => updateSetting(def.key, e.target.value)}
                    className="si-input w-full font-mono"
                />
            );
        }

        return (
            <input
                type="number"
                min={def.min}
                max={def.max}
                value={value || def.default}
                onChange={(e) => updateSetting(def.key, parseInt(e.target.value) || def.default)}
                className="si-input w-full font-mono"
            />
        );
    };

    return (
        <GenericIngestionLayout
            endpoints={endpoints}
            currentJobId={currentJobId}
            onSelectJob={setCurrentJobId}
            onJobStarted={setCurrentJobId}
        >
            <div className="h-full flex flex-col p-4 md:p-6 animate-fade-in overflow-y-auto">
                <div className="max-w-3xl mx-auto w-full space-y-4 md:space-y-6">
                    <h2 className="text-lg md:text-2xl font-bold flex items-center gap-2" style={{ color: 'var(--text-primary)' }}>
                        <FaSyncAlt style={{ color: 'var(--accent)' }} /> Avatar Sync
                    </h2>

                    {/* Info Panel */}
                    <div className="glass-panel rounded-xl p-5 shadow-lg" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
                        <p className="text-sm leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
                            Fetches avatars from Signal CDN, decrypts with AES-256-GCM, and compares using{' '}
                            <strong style={{ color: 'var(--text-primary)' }}>SSIM visual similarity</strong> to detect actual changes.
                            Avatars are prioritized by change frequency:{' '}
                            <span className="font-semibold" style={{ color: 'var(--warning)' }}>HIGH</span>{' '}
                            <span style={{ color: 'var(--text-tertiary)' }}>({settings.AVATAR_SYNC_CHECK_HIGH_FREQ_HOURS || 6}h)</span>,{' '}
                            <span className="font-semibold" style={{ color: 'var(--accent)' }}>MEDIUM</span>{' '}
                            <span style={{ color: 'var(--text-tertiary)' }}>({settings.AVATAR_SYNC_CHECK_MEDIUM_FREQ_HOURS || 72}h)</span>,{' '}
                            <span className="font-semibold" style={{ color: 'var(--text-secondary)' }}>LOW</span>{' '}
                            <span style={{ color: 'var(--text-tertiary)' }}>({settings.AVATAR_SYNC_CHECK_LOW_FREQ_HOURS || 168}h)</span>.
                        </p>
                    </div>

                    {/* Configuration Panel */}
                    <div className="glass-panel rounded-xl shadow-lg" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
                        <div className="p-4 md:p-5 flex flex-wrap items-center justify-between gap-2" style={{ borderBottom: '1px solid var(--border)' }}>
                            <h3 className="text-lg font-bold flex items-center gap-2" style={{ color: 'var(--text-primary)' }}>
                                <FaCogs style={{ color: 'var(--text-secondary)' }} /> Configuration
                            </h3>
                            <div className="flex items-center gap-3">
                                {hasChanges && (
                                    <span className="text-[10px] uppercase tracking-wider font-bold animate-pulse" style={{ color: 'var(--warning)' }}>
                                        Unsaved changes
                                    </span>
                                )}
                                <button
                                    onClick={handleSaveConfig}
                                    disabled={configLoading || !hasChanges}
                                    className={`flex items-center gap-1.5 px-4 py-1.5 rounded font-bold text-xs transition-all ${hasChanges
                                        ? 'si-button-primary shadow-lg'
                                        : 'cursor-not-allowed'
                                        }`}
                                    style={!hasChanges ? { background: 'var(--bg-hover)', color: 'var(--text-tertiary)' } : undefined}
                                >
                                    <PiFloppyDiskBold />
                                    {configLoading ? "Saving..." : "Save All"}
                                </button>
                            </div>
                        </div>

                        {message && (
                            <div className="mx-5 mt-4 text-xs p-2.5 rounded" style={{ background: 'var(--success-bg)', color: 'var(--success)', border: '1px solid var(--success)' }}>
                                {message}
                            </div>
                        )}
                        {configError && (
                            <div className="mx-5 mt-4 text-xs p-2.5 rounded" style={{ background: 'var(--danger-bg)', color: 'var(--danger)', border: '1px solid var(--danger)' }}>
                                {configError}
                            </div>
                        )}

                        <div>
                            {SETTING_GROUPS.map((group, groupIdx) => {
                                const isExpanded = expandedGroup === group.label;
                                return (
                                    <div key={group.label} style={groupIdx > 0 ? { borderTop: '1px solid var(--border)' } : undefined}>
                                        <button
                                            onClick={() => setExpandedGroup(isExpanded ? null : group.label)}
                                            className="w-full flex items-center justify-between px-5 py-3.5 transition-colors"
                                            onMouseEnter={(e) => e.currentTarget.style.background = 'var(--bg-hover)'}
                                            onMouseLeave={(e) => e.currentTarget.style.background = ''}
                                        >
                                            <div className="flex items-center gap-2.5">
                                                {group.icon}
                                                <span className="text-sm font-bold" style={{ color: 'var(--text-primary)' }}>{group.label}</span>
                                                <span className="text-[10px] font-mono" style={{ color: 'var(--text-tertiary)' }}>
                                                    ({group.settings.length} settings)
                                                </span>
                                            </div>
                                            <svg
                                                className={`w-4 h-4 transition-transform ${isExpanded ? 'rotate-180' : ''}`}
                                                style={{ color: 'var(--text-tertiary)' }}
                                                fill="none" viewBox="0 0 24 24" stroke="currentColor"
                                            >
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                                            </svg>
                                        </button>

                                        {isExpanded && (
                                            <div className="px-3 md:px-5 pb-4 grid grid-cols-1 md:grid-cols-2 gap-3 animate-fade-in">
                                                {group.settings.map((def) => {
                                                    const isChanged = settings[def.key] !== savedSettings[def.key];
                                                    return (
                                                        <div key={def.key} className="rounded-lg p-3 transition-colors"
                                                            style={isChanged
                                                                ? { background: 'color-mix(in srgb, var(--accent) 5%, transparent)', border: '1px solid var(--accent)' }
                                                                : { background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
                                                            <label className="si-label block mb-1.5">
                                                                {def.label}
                                                            </label>
                                                            {renderSettingInput(def)}
                                                            <p className="text-[10px] mt-1.5" style={{ color: 'var(--text-tertiary)' }}>{def.description}</p>
                                                        </div>
                                                    );
                                                })}
                                            </div>
                                        )}
                                    </div>
                                );
                            })}
                        </div>
                    </div>

                    {/* Manual Trigger Panel */}
                    <div className="glass-panel rounded-xl p-4 md:p-5 shadow-lg relative overflow-hidden group" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
                        <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity hidden md:block">
                            <FaPlay className="text-9xl" style={{ color: 'var(--accent)' }} />
                        </div>

                        <h3 className="text-base md:text-lg font-bold mb-3 flex items-center gap-2 relative z-10" style={{ color: 'var(--text-primary)' }}>
                            <FaPlay style={{ color: 'var(--accent)' }} /> Manual Trigger
                        </h3>

                        <p className="text-sm mb-5 relative z-10 max-w-lg" style={{ color: 'var(--text-secondary)' }}>
                            Manually trigger avatar sync now. Smart filtering will skip recently verified
                            profiles based on the tier intervals configured above.
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
                                <><FaSyncAlt /> Run Avatar Sync Now</>
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

export default AvatarSync;
