import React, { useState, useEffect, useRef, useMemo } from "react";
import {
    PiFolderOpenBold,
    PiFileCodeBold,
    PiCloudArrowUpBold,
    PiCheckBold,
    PiWarningBold,
    PiXBold,
    PiSpinnerGapBold,
    PiClockCounterClockwiseBold,
    PiArticleBold,
    PiTerminalWindowBold,
    PiArrowLeftBold,
    PiWarningCircleBold,
    PiDownloadSimpleBold,
    PiFileArrowDownBold,
    PiArrowCounterClockwiseBold,
    PiUserCircleBold,
    PiEnvelopeSimpleBold,
    PiShieldCheckBold,
    PiCircleBold,
    PiUserBold,
    PiCaretDownBold,
    PiCaretUpBold,
} from "react-icons/pi";
import { format } from "date-fns";
import apiClient from "../../../services/api";
import useIsMobile from "../../../hooks/useIsMobile";

// --- Icons ---
const Spinner = () => <PiSpinnerGapBold className="animate-spin text-lg" />;

// --- Helper Functions ---
// --- Helper Functions ---
const formatDuration = (start, end) => {
    if (!start) return '-';
    const s = new Date(start).getTime();
    const e = end ? new Date(end).getTime() : Date.now();
    const diff = Math.max(0, e - s);

    const sec = Math.floor(diff / 1000) % 60;
    const min = Math.floor(diff / (1000 * 60)) % 60;
    const hr = Math.floor(diff / (1000 * 60 * 60));

    if (hr > 0) return `${hr}h ${min}m ${sec}s`;
    if (min > 0) return `${min}m ${sec}s`;
    return `${sec}s`;
};

const getStatusStyle = (status) => {
    switch (status) {
        case "completed": return { color: 'var(--success)', borderColor: 'var(--success)', background: 'var(--success-bg)' };
        case "failed": return { color: 'var(--danger)', borderColor: 'var(--danger)', background: 'var(--danger-bg)' };
        case "processing": return { color: 'var(--accent)', borderColor: 'var(--accent)', background: 'color-mix(in srgb, var(--accent) 10%, transparent)' };
        case "queued": return { color: 'var(--warning)', borderColor: 'var(--warning)', background: 'var(--warning-bg)' };
        default: return { color: 'var(--text-secondary)', borderColor: 'var(--border)', background: 'var(--bg-hover)' };
    }
};

const STEP_NAMES = {
    "processing_users": "Processing Users",
    "extracting_groups": "Extracting Groups",
    "extracting_memberships": "Extracting Memberships",
    "revert_ingestion": "Reverting Ingestion",
    "indexing_users": "Indexing Users",
    "indexing_groups": "Indexing Groups",
    "recording_history": "Recording History",
    "cleanup_staging": "Cleanup",
    "processing_groups": "Processing Groups", // Legacy
    "processing_avatars": "Processing Avatars" // Legacy
};

export const JobStep = ({ step, isLast, logs = [] }) => {
    const isCompleted = step.status === "completed";
    const isFailed = step.status === "failed";
    const isRunning = step.status === "running";
    const isPending = step.status === "pending";

    const displayName = STEP_NAMES[step.step_name] || step.step_name;

    // Filter logs for this step to show "Completed Substeps"
    const stepLogs = logs
        .filter(l => l.step_name === step.step_name)
        .sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));

    // Calculate Duration
    const duration = (step.started_at)
        ? formatDuration(step.started_at, step.completed_at)
        : null;

    return (
        <div className="relative pl-8 pb-8 last:pb-0">
            {/* Timeline Line Container */}
            {!isLast && (
                <>
                    {/* Background Line */}
                    <div className="absolute left-[11px] top-6 bottom-0 w-0.5" style={{ background: 'var(--border)' }} />
                    {/* Progress Line (Animated) */}
                    <div
                        className={`absolute left-[11px] top-6 w-0.5 transition-all duration-500 ease-out ${isRunning ? "shadow-[0_0_10px_rgba(59,130,246,0.5)]" : ""
                            }`}
                        style={{
                            background: isCompleted ? 'var(--success)' : isRunning ? 'var(--accent)' : 'transparent',
                            opacity: isCompleted ? 0.5 : 1,
                            height: isCompleted ? undefined : isRunning ? `${Math.max(step.progress_percentage || 0, 0)}%` : 0,
                            bottom: isCompleted ? 0 : undefined
                        }}
                    />
                </>
            )}

            {/* Icon/Dot */}
            <div className={`absolute left-0 top-0 w-6 h-6 rounded-full flex items-center justify-center z-10 transition-all ${isRunning ? "animate-pulse" : ""}`}
                style={{
                    borderWidth: '1px', borderStyle: 'solid',
                    ...(isCompleted
                        ? { background: 'var(--success-bg)', borderColor: 'var(--success)', color: 'var(--success)', boxShadow: '0 0 10px rgba(16,185,129,0.2)' }
                        : isFailed
                            ? { background: 'var(--danger-bg)', borderColor: 'var(--danger)', color: 'var(--danger)', boxShadow: '0 0 10px rgba(244,63,94,0.2)' }
                            : isRunning
                                ? { background: 'color-mix(in srgb, var(--accent) 20%, transparent)', borderColor: 'var(--accent)', color: 'var(--accent)', boxShadow: '0 0 10px rgba(59,130,246,0.3)' }
                                : { background: 'var(--bg-hover)', borderColor: 'var(--border)', color: 'var(--text-tertiary)' })
                }}>
                {isCompleted ? <PiCheckBold className="text-xs" /> :
                    isFailed ? <PiXBold className="text-xs" /> :
                        isRunning ? <Spinner /> :
                            <div className="w-1.5 h-1.5 rounded-full bg-current opacity-50" />}
            </div>

            {/* Content Card */}
            <div className="rounded-lg p-3 transition-all ml-1"
                style={{
                    borderWidth: '1px', borderStyle: 'solid',
                    ...(isRunning
                        ? { background: 'var(--bg-hover)', borderColor: 'var(--accent)' }
                        : { background: 'color-mix(in srgb, var(--bg-hover) 30%, transparent)', borderColor: 'var(--border)' })
                }}>
                <div className="flex justify-between items-start mb-2">
                    <span className="text-sm font-bold"
                        style={{ color: isCompleted ? 'var(--text-primary)' : isFailed ? 'var(--danger)' : isRunning ? 'var(--accent)' : 'var(--text-tertiary)' }}>
                        {displayName}
                    </span>
                    <div className="flex flex-col items-end">
                        {step.progress_percentage > 0 && (
                            <span className="text-[10px] font-mono" style={{ color: isRunning ? 'var(--accent)' : 'var(--text-tertiary)' }}>
                                {step.progress_percentage?.toFixed(0)}%
                            </span>
                        )}
                        {duration && (
                            <span className="text-[10px] font-mono" style={{ color: 'var(--text-tertiary)' }}>
                                {duration}
                            </span>
                        )}
                    </div>
                </div>

                {/* Substeps: Structured Checklist OR Legacy Logs */}
                {step.substeps && step.substeps.length > 0 ? (
                    <div className="mb-3 space-y-1">
                        {step.substeps.map((sub, idx) => {
                            const isSubCompleted = sub.status === "completed";
                            const isSubRunning = sub.status === "running";
                            const isSubActive = isSubRunning || (isRunning && sub.status !== 'completed' && step.current_action === sub.name);

                            return (
                                <div key={idx} className="flex items-start gap-2 text-[11px] pl-1 ml-0.5 transition-all"
                                    style={{
                                        borderLeft: '2px solid',
                                        ...(isSubCompleted
                                            ? { borderColor: 'var(--success)', color: 'var(--text-secondary)' }
                                            : isSubActive
                                                ? { borderColor: 'var(--accent)', color: 'var(--accent)', fontWeight: 500, background: 'color-mix(in srgb, var(--accent) 5%, transparent)' }
                                                : { borderColor: 'var(--border)', color: 'var(--text-tertiary)' })
                                    }}>
                                    {isSubCompleted ? (
                                        <PiCheckBold className="shrink-0 mt-0.5" style={{ color: 'var(--success)' }} />
                                    ) : isSubActive ? (
                                        <PiSpinnerGapBold className="shrink-0 mt-0.5 animate-spin" style={{ color: 'var(--accent)' }} />
                                    ) : (
                                        <div className="w-2.5 h-2.5 rounded-full mt-0.5 shrink-0" style={{ border: '1px solid var(--border)' }} />
                                    )}
                                    <span className={`${isSubCompleted ? "opacity-75 line-through" : ""}`}
                                        style={isSubCompleted ? { textDecorationColor: 'var(--text-tertiary)' } : undefined}>
                                        {sub.name}
                                    </span>
                                </div>
                            );
                        })}
                    </div>
                ) : null}

                {/* Current Active Substep */}
                {isRunning && (
                    <div className="rounded p-2 mb-2 flex items-center gap-2 animate-pulse"
                        style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
                        <Spinner />
                        <span className="text-xs font-mono" style={{ color: 'var(--accent)' }}>
                            {step.current_action || "Processing..."}
                        </span>
                    </div>
                )}

                {/* Final Status Message if not running but has action */}
                {!isRunning && step.current_action && (
                    <div className="text-[10px] font-mono italic mb-2" style={{ color: 'var(--text-tertiary)' }}>
                        Last: {step.current_action}
                    </div>
                )}

                {/* Progress Bar */}
                <div className="h-1 rounded-full overflow-hidden" style={{ background: 'var(--bg-card)' }}>
                    <div
                        className="h-full transition-all duration-300 ease-out"
                        style={{
                            width: `${step.progress_percentage || 0}%`,
                            background: isCompleted ? 'var(--success)' : isFailed ? 'var(--danger)' : 'var(--accent)',
                            boxShadow: isRunning ? '0 0 10px var(--accent)' : undefined
                        }}
                    />
                </div>
            </div>
        </div>
    );
};


export const JobMonitor = ({ jobId, endpoints, job, onNewJob, onBack, onSwitchJob }) => {
    const isMobile = useIsMobile();
    const [logs, setLogs] = useState([]);
    const [steps, setSteps] = useState([]);
    const [jobData, setJobData] = useState(null); // Track full job data
    const [status, setStatus] = useState("pending");
    const [autoScroll, setAutoScroll] = useState(false);
    const [logFilter, setLogFilter] = useState("ALL"); // ALL, INFO, WARNING, ERROR
    const [logLimit, setLogLimit] = useState(100); // 100, 200, 500, 1000
    const [logsExpanded, setLogsExpanded] = useState(false); // collapsed on mobile by default
    const [showLogSheet, setShowLogSheet] = useState(false);

    // Pagination State
    const [hasMoreLogs, setHasMoreLogs] = useState(true);
    const [isLoadingMore, setIsLoadingMore] = useState(false);

    // ACTION State
    const [actionLoading, setActionLoading] = useState(false);

    // Failures Panel State
    const [showFailures, setShowFailures] = useState(false);
    const [failures, setFailures] = useState([]);
    const [failuresSummary, setFailuresSummary] = useState({});
    const [failuresTotal, setFailuresTotal] = useState(0);
    const [failuresLoading, setFailuresLoading] = useState(false);
    const [failuresFilter, setFailuresFilter] = useState("all"); // all, error, missing
    const [failuresOffset, setFailuresOffset] = useState(0);
    const FAILURES_LIMIT = 100;

    // Refs
    const logContainerRef = useRef(null);
    const logEndRef = useRef(null);
    const prevScrollHeight = useRef(0);

    // Reset state on job change
    // Polling State
    const lastLogIdRef = useRef(0);

    // Reset state on job change
    useEffect(() => {
        setLogs([]);
        setSteps([]);
        setJobData(job);
        setStatus("pending");
        // setAutoScroll(job?.status === 'running');
        setLogFilter("ALL");
        setLogLimit(100);
        setHasMoreLogs(true);
        lastLogIdRef.current = 0;
        setShowFailures(false);
        setFailures([]);
        setFailuresSummary({});
        setFailuresTotal(0);
        setFailuresFilter("all");
        setFailuresOffset(0);
    }, [jobId]);

    // Track whether we've done the final log fetch after job finished
    const finalLogsFetchedRef = useRef(false);

    // Reset final logs ref on job change
    useEffect(() => {
        finalLogsFetchedRef.current = false;
    }, [jobId]);

    // Polling Logic (Progress & "Fresh" Logs)
    useEffect(() => {
        let shouldPoll = true;
        const pollInterval = 2000;
        let currentStatus = status; // Track latest status within this effect

        const isFinished = (s) => ["completed", "failed", "rolled_back"].includes(s?.toLowerCase());

        const fetchProgress = async () => {
            if (!shouldPoll) return;
            try {
                const { data } = await apiClient.get(`${endpoints.progress}/${jobId}`);
                currentStatus = data.status;
                setStatus(data.status);
                setJobData(data);
                const sortedSteps = (data.steps || []).sort((a, b) => a.id - b.id);
                setSteps(sortedSteps);
            } catch (e) {
                console.error("Poll error", e);
            }
            if (shouldPoll && !isFinished(currentStatus)) {
                setTimeout(fetchProgress, pollInterval);
            }
        };

        const fetchLiveLogs = async () => {
            if (!shouldPoll) return;

            // If job is finished and we already did a final fetch, stop
            if (isFinished(currentStatus) && finalLogsFetchedRef.current) return;

            try {
                const lastId = logs.length > 0 ? logs[logs.length - 1].id : undefined;
                const params = { limit: 100 };
                if (lastId) {
                    params.after_id = lastId;
                }

                const { data } = await apiClient.get(`${endpoints.progress}/${jobId}/logs`, { params });

                if (Array.isArray(data) && data.length > 0) {
                    const newLogsAsc = [...data].reverse();
                    if (lastId) {
                        setLogs(prev => [...prev, ...newLogsAsc]);
                    } else {
                        setLogs(newLogsAsc);
                    }
                }

                // Mark final fetch done if job is finished
                if (isFinished(currentStatus)) {
                    finalLogsFetchedRef.current = true;
                }
            } catch (e) { console.error(e); }

            if (shouldPoll && !isFinished(currentStatus)) {
                setTimeout(fetchLiveLogs, pollInterval);
            }
        };

        fetchProgress();
        fetchLiveLogs();

        return () => { shouldPoll = false; };
    }, [jobId, endpoints.progress, status, logs.length]);

    // Filtered Logs
    const filteredLogs = useMemo(() => {
        if (logFilter === "ALL") return logs;
        return logs.filter(log => log.log_level === logFilter);
    }, [logs, logFilter]);

    const errorLogs = useMemo(() => {
        return logs.filter(log => log.log_level === "ERROR");
    }, [logs]);

    // Auto-scroll
    useEffect(() => {
        if (autoScroll && logEndRef.current) {
            logEndRef.current.scrollIntoView({ behavior: "smooth" });
        }
    }, [logs, autoScroll]);

    // Infinite Scroll / Pagination Handler
    const handleScroll = async (e) => {
        const { scrollTop, scrollHeight } = e.currentTarget;

        // If scrolled to top and NOT loading and has more
        if (scrollTop === 0 && !isLoadingMore && hasMoreLogs && logs.length >= logLimit) {
            setIsLoadingMore(true);
            prevScrollHeight.current = scrollHeight;

            try {
                // Fetch NEXT page
                // offset = current count
                const { data } = await apiClient.get(`${endpoints.progress}/${jobId}/logs`, {
                    params: { limit: logLimit, offset: logs.length }
                });

                if (Array.isArray(data) && data.length > 0) {
                    const olderLogsAsc = [...data].reverse();
                    setLogs(prev => [...olderLogsAsc, ...prev]);

                    setTimeout(() => {
                        if (logContainerRef.current) {
                            const newScrollHeight = logContainerRef.current.scrollHeight;
                            logContainerRef.current.scrollTop = newScrollHeight - prevScrollHeight.current;
                        }
                    }, 0);
                } else {
                    setHasMoreLogs(false);
                }
            } catch (err) {
                console.error("Failed to load more logs", err);
            } finally {
                setIsLoadingMore(false);
            }
        }
    };

    // Fetch failures list
    const fetchFailures = async (filter = failuresFilter, off = 0) => {
        setFailuresLoading(true);
        try {
            const params = { limit: FAILURES_LIMIT, offset: off };
            if (filter !== "all") params.action = filter;
            const { data } = await apiClient.get(`/ingest/avatar-sync/${jobId}/failures`, { params });
            setFailures(off > 0 ? prev => [...prev, ...data.items] : data.items);
            setFailuresSummary(data.summary || {});
            setFailuresTotal(data.total || 0);
            setFailuresOffset(off);
        } catch (e) {
            console.error("Failed to fetch failures", e);
        } finally {
            setFailuresLoading(false);
        }
    };

    const handleShowFailures = () => {
        if (!showFailures) {
            fetchFailures("all", 0);
        }
        setShowFailures(!showFailures);
    };

    const handleFailuresFilterChange = (newFilter) => {
        setFailuresFilter(newFilter);
        setFailuresOffset(0);
        fetchFailures(newFilter, 0);
    };

    const handleLoadMoreFailures = () => {
        const nextOffset = failuresOffset + FAILURES_LIMIT;
        fetchFailures(failuresFilter, nextOffset);
    };

    // Actions
    const handleReprocess = async () => {
        if (!window.confirm("Are you sure you want to reprocess this job? This will create a NEW job using the same source file.")) return;
        setActionLoading(true);
        try {
            // Strip query params if present (e.g. /jobs/?type=x -> /jobs)
            const baseUrl = endpoints.jobs.split('?')[0];
            const { data } = await apiClient.post(`${baseUrl}${jobId}/reprocess`);
            alert(`Reprocess started: Job #${data.job_id}`);
            // Switch to new job
            if (onSwitchJob) onSwitchJob(data.job_id);
        } catch (e) {
            console.error(e);
            alert("Reprocess Failed: " + (e.response?.data?.detail || e.message));
        } finally {
            setActionLoading(false);
        }
    };

    const handleStop = async () => {
        if (!window.confirm("Are you sure you want to stop this job? It will be marked as failed.")) return;
        setActionLoading(true);
        try {
            await apiClient.post(`/ingest/avatar-sync/${jobId}/stop`);
            setStatus("failed");
        } catch (e) {
            alert("Stop Failed: " + (e.response?.data?.detail || e.message));
        } finally {
            setActionLoading(false);
        }
    };

    const handleRollback = async () => {
        const reason = prompt("Enter a reason for rolling back this ingestion:");
        if (!reason) return;

        setActionLoading(true);
        try {
            const jobsBaseUrl = endpoints.jobs.split('?')[0];
            const rollbackUrl = endpoints.rollback
                ? `${endpoints.rollback}/${jobId}/rollback`
                : `${jobsBaseUrl}/${jobId}/rollback`;
            const { data } = await apiClient.post(rollbackUrl, { reason });
            alert(`Rollback Job #${data.job_id} created.`);
            // Switch to new job
            if (onSwitchJob) onSwitchJob(data.job_id);
        } catch (e) {
            console.error(e);
            alert("Rollback Failed: " + (e.response?.data?.detail || e.message));
        } finally {
            setActionLoading(false);
        }
    };

    const handleDownloadLogs = async () => {
        try {
            const { data } = await apiClient.get(`${endpoints.progress}/${jobId}/logs`, { params: { limit: 100000 } });
            if (!Array.isArray(data)) return;
            // Data is DESC. Sort ASC for file
            const sorted = [...data].sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));
            const text = sorted.map(l => `[${l.timestamp}] [${l.log_level}] ${l.message}`).join("\n");

            const blob = new Blob([text], { type: "text/plain" });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `job_${jobId}_full.log`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        } catch (e) {
            alert("Failed to download logs");
        }
    };

    // Export avatar sync report as JSON
    const handleExportReport = () => {
        const m = jobData?.metrics || job?.metrics;
        if (!m) return;
        const report = {
            job_id: jobId,
            status: status,
            ingestion_type: jobData?.ingestion_type,
            created_at: jobData?.created_at,
            completed_at: jobData?.completed_at,
            summary: {
                total_eligible: m.total_eligible || 0,
                total_checked: m.total_checked || 0,
                changed: m.changed || 0,
                new: m.new || 0,
                unchanged: m.unchanged || 0,
                errors: m.errors || 0,
                missing: m.missing || 0,
                total_failed: (m.errors || 0) + (m.missing || 0),
                batches_processed: m.batches_processed || 0,
            }
        };
        const blob = new Blob([JSON.stringify(report, null, 2)], { type: "application/json" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `avatar_sync_job_${jobId}_report.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    };

    // Metrics Helper
    const metrics = jobData?.metrics || job?.metrics;

    // Status icon style
    const statusIconStyle = status === 'completed' ? { background: 'var(--success)', color: 'white', borderColor: 'var(--success)' }
        : status === 'failed' ? { background: 'var(--danger)', color: 'white', borderColor: 'var(--danger)' }
            : status === 'rolled_back' ? { background: 'var(--warning)', color: 'white', borderColor: 'var(--warning)' }
                : status === 'queued' ? { background: 'var(--warning)', color: 'white', borderColor: 'var(--warning)' }
                    : { background: 'var(--accent)', color: 'white', borderColor: 'var(--accent)' };

    return (
        <div className={`flex flex-col animate-fade-in${!isMobile ? ' h-full backdrop-blur-sm overflow-hidden' : ''}`} style={{ background: 'var(--bg-card)' }}>
            {/* Header */}
            <div className="px-3 py-3 md:px-4 flex items-center gap-2 shrink-0" style={{ background: 'var(--bg-card)', borderBottom: '1px solid var(--border)' }}>
                {/* Back button (mobile only) */}
                <button
                    onClick={onBack}
                    className="md:hidden flex-shrink-0 p-1.5 rounded-lg transition-colors"
                    style={{ color: 'var(--text-secondary)' }}
                    onMouseEnter={(e) => { e.currentTarget.style.color = 'var(--text-primary)'; e.currentTarget.style.background = 'var(--bg-hover)'; }}
                    onMouseLeave={(e) => { e.currentTarget.style.color = 'var(--text-secondary)'; e.currentTarget.style.background = ''; }}
                >
                    <PiArrowLeftBold className="text-base" />
                </button>

                {/* Status icon */}
                <div className={`flex-shrink-0 w-8 h-8 md:w-10 md:h-10 rounded-xl flex items-center justify-center text-base md:text-xl shadow-lg ${status === 'queued' || status === 'processing' ? 'animate-pulse' : ''}`}
                    style={{ ...statusIconStyle, borderWidth: '1px', borderStyle: 'solid' }}>
                    {status === 'completed' ? <PiCheckBold /> :
                        status === 'failed' ? <PiXBold /> :
                            status === 'rolled_back' ? <PiArrowCounterClockwiseBold /> :
                                status === 'queued' ? <PiClockCounterClockwiseBold /> :
                                    <Spinner />}
                </div>

                {/* Job info — takes remaining space, truncates */}
                <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1.5 flex-wrap">
                        <h3 className="font-bold text-sm flex-shrink-0" style={{ color: 'var(--text-primary)' }}>
                            {`Job #${jobId}`}
                        </h3>
                        <span className={`flex-shrink-0 px-1.5 py-0.5 rounded text-[10px] uppercase ${status === 'processing' ? 'animate-pulse' : ''}`}
                            style={{ ...getStatusStyle(status), borderWidth: '1px', borderStyle: 'solid' }}>
                            {status}
                        </span>
                    </div>
                    {jobData?.created_at && (
                        <div className="text-[10px] font-mono mt-0.5" style={{ color: 'var(--text-secondary)' }}>
                            <span>Time: <span style={{ color: 'var(--text-primary)' }}>{formatDuration(jobData.created_at, jobData.completed_at || (status === 'completed' || status === 'failed' ? undefined : new Date()))}</span></span>
                        </div>
                    )}
                </div>

                {/* Action buttons */}
                <div className="flex-shrink-0 flex items-center gap-1.5">
                    {/* Stop — desktop only */}
                    {(status === 'running' || status === 'pending' || status === 'queued') && jobData?.ingestion_type === 'avatar_sync' && (
                        <button onClick={handleStop} disabled={actionLoading}
                            className="hidden sm:flex items-center gap-1 px-2 py-1 rounded text-[10px] transition-all"
                            style={{ background: 'var(--bg-hover)', border: '1px solid var(--border)', color: 'var(--danger)' }}
                            onMouseEnter={(e) => { e.currentTarget.style.background = 'var(--danger-bg)'; e.currentTarget.style.borderColor = 'var(--danger)'; }}
                            onMouseLeave={(e) => { e.currentTarget.style.background = 'var(--bg-hover)'; e.currentTarget.style.borderColor = 'var(--border)'; }}
                        >
                            <PiXBold /> Stop
                        </button>
                    )}

                    {/* Export / Reprocess — desktop only */}
                    {(status === 'completed' || status === 'failed') && (
                        <>
                            {jobData?.ingestion_type === 'avatar_sync' && (
                                <button onClick={handleExportReport}
                                    className="hidden sm:flex items-center gap-1 px-2 py-1 rounded text-[10px] transition-all"
                                    style={{ background: 'var(--bg-hover)', border: '1px solid var(--border)', color: 'var(--text-primary)' }}
                                >
                                    <PiFileArrowDownBold /> Export
                                </button>
                            )}
                            <button onClick={handleReprocess} disabled={actionLoading}
                                className="hidden sm:flex items-center gap-1 px-2 py-1 rounded text-[10px] transition-all"
                                style={{ background: 'var(--bg-hover)', border: '1px solid var(--border)', color: 'var(--text-primary)' }}
                            >
                                <PiArrowCounterClockwiseBold /> Reprocess
                            </button>
                        </>
                    )}

                    {/* New button — icon-only on mobile, icon+text on desktop */}
                    <button
                        onClick={onNewJob}
                        className="si-button-primary flex items-center gap-1.5 px-2.5 py-1.5 md:px-3 md:py-2"
                    >
                        <PiCloudArrowUpBold className="text-base" />
                        <span className="hidden sm:inline text-xs">New</span>
                    </button>
                </div>
            </div>

            {/* Error Message Banner */}
            {jobData?.error_message && (
                <div className="p-2 text-xs px-4 flex gap-2" style={{ background: 'var(--danger-bg)', borderBottom: '1px solid var(--danger)', color: 'var(--danger)' }}>
                    <PiWarningCircleBold className="text-lg shrink-0" />
                    <span className="font-mono max-h-[100px] overflow-auto">{jobData.error_message}</span>
                </div>
            )}

            {/* Metrics Bar */}
            {metrics && jobData?.ingestion_type === 'avatar_sync' ? (
                <div className="shrink-0" style={{ background: 'var(--bg-card)', borderBottom: '1px solid var(--border)' }}>
                    {/* Progress bar */}
                    {(jobData?.status === 'running' || jobData?.status === 'queued') && metrics.total_eligible > 0 && (
                        <div className="px-4 pt-3 pb-1">
                            <div className="flex justify-between items-center mb-1">
                                <span className="text-[10px] font-mono" style={{ color: 'var(--text-secondary)' }}>
                                    {metrics.total_checked || 0} / {metrics.total_eligible} users processed
                                </span>
                                <span className="text-[10px] font-mono font-bold" style={{ color: 'var(--accent)' }}>
                                    {metrics.total_eligible > 0 ? Math.min(100, Math.round((metrics.total_checked / metrics.total_eligible) * 100)) : 0}%
                                </span>
                            </div>
                            <div className="h-2 rounded-full overflow-hidden" style={{ background: 'var(--bg-hover)' }}>
                                <div
                                    className="h-full rounded-full transition-all duration-500 ease-out"
                                    style={{ background: 'var(--accent)', width: `${metrics.total_eligible > 0 ? Math.min(100, (metrics.total_checked / metrics.total_eligible) * 100) : 0}%`, boxShadow: '0 0 8px rgba(59,130,246,0.4)' }}
                                />
                            </div>
                        </div>
                    )}
                    <div className="grid grid-cols-2 lg:grid-cols-4 gap-2 lg:gap-4 p-2 lg:p-4">
                        <div className="p-2 rounded flex justify-between items-center" style={{ background: 'var(--bg-hover)', border: '1px solid var(--border)' }}>
                            <div>
                                <div className="text-[9px] uppercase font-bold" style={{ color: 'var(--text-tertiary)' }}>Checked</div>
                                <div className="text-lg font-bold leading-none" style={{ color: 'var(--text-primary)' }}>{metrics.total_checked || 0}</div>
                            </div>
                            <div className="text-[9px] text-right" style={{ color: 'var(--text-tertiary)' }}>
                                <div>{metrics.batches_processed || 0} batches</div>
                                {metrics.shard_count > 1 && <div>{metrics.shards_completed || 0}/{metrics.shard_count} shards</div>}
                            </div>
                        </div>
                        <div className="p-2 rounded flex justify-between items-center" style={{ background: 'var(--bg-hover)', border: '1px solid var(--border)' }}>
                            <div>
                                <div className="text-[9px] uppercase font-bold" style={{ color: 'var(--text-tertiary)' }}>Changed</div>
                                <div className="text-lg font-bold leading-none" style={{ color: 'var(--warning)' }}>{metrics.changed || 0}</div>
                            </div>
                            <div className="text-[9px] text-right" style={{ color: 'var(--text-tertiary)' }}>
                                <div>{metrics.new || 0} new</div>
                            </div>
                        </div>
                        <div className="p-2 rounded flex justify-between items-center" style={{ background: 'var(--bg-hover)', border: '1px solid var(--border)' }}>
                            <div>
                                <div className="text-[9px] uppercase font-bold" style={{ color: 'var(--text-tertiary)' }}>Unchanged</div>
                                <div className="text-lg font-bold leading-none" style={{ color: 'var(--success)' }}>{metrics.unchanged || 0}</div>
                            </div>
                        </div>
                        <div
                            className="p-2 rounded flex justify-between items-center cursor-pointer transition-all"
                            style={{
                                background: showFailures ? 'var(--danger-bg)' : 'var(--bg-hover)',
                                border: showFailures ? '1px solid var(--danger)' : '1px solid var(--border)',
                            }}
                            onClick={handleShowFailures}
                            title="Click to view failed service IDs"
                        >
                            <div>
                                <div className="text-[9px] uppercase font-bold" style={{ color: 'var(--text-tertiary)' }}>Errors</div>
                                <div className="text-lg font-bold leading-none" style={{ color: 'var(--danger)' }}>{(metrics.errors || 0) + (metrics.missing || 0)}</div>
                            </div>
                            <div className="text-[9px] text-right" style={{ color: 'var(--text-tertiary)' }}>
                                <div>{metrics.missing || 0} missing</div>
                                <div>{metrics.errors || 0} failed</div>
                                <div className="mt-1 underline" style={{ color: 'var(--danger)' }}>{showFailures ? 'Hide' : 'View'} IDs</div>
                            </div>
                        </div>
                    </div>

                    {/* Failures Detail Panel */}
                    {showFailures && (
                        <div style={{ borderBottom: '1px solid var(--border)', background: 'var(--bg-card)' }}>
                            <div className="px-4 py-1.5 flex items-center justify-between" style={{ borderBottom: '1px solid var(--border)' }}>
                                <span className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-widest" style={{ color: 'var(--text-secondary)' }}>
                                    <PiWarningCircleBold className="text-sm" /> Failed Service IDs ({failuresTotal})
                                </span>
                                <div className="flex items-center gap-2">
                                    <select
                                        className="si-select-sm"
                                        value={failuresFilter}
                                        onChange={(e) => handleFailuresFilterChange(e.target.value)}
                                    >
                                        <option value="all">All Failures</option>
                                        <option value="error">Errors Only</option>
                                        <option value="missing">Missing Only</option>
                                    </select>
                                    <button
                                        onClick={() => setShowFailures(false)}
                                        className="text-[9px] px-1.5 py-0.5 rounded-full transition-colors"
                                        style={{ background: 'var(--bg-hover)', color: 'var(--text-tertiary)' }}
                                    >
                                        Close
                                    </button>
                                </div>
                            </div>
                            {failuresSummary && (Object.keys(failuresSummary).length > 0) && (
                                <div className="px-4 py-1 flex gap-3 text-[9px]" style={{ color: 'var(--text-tertiary)' }}>
                                    {failuresSummary.error > 0 && (
                                        <span><strong style={{ color: 'var(--text-secondary)' }}>{failuresSummary.error}</strong> errors</span>
                                    )}
                                    {failuresSummary.missing > 0 && (
                                        <span><strong style={{ color: 'var(--text-secondary)' }}>{failuresSummary.missing}</strong> missing</span>
                                    )}
                                </div>
                            )}
                            <div className="max-h-52 overflow-y-auto custom-scrollbar px-4 pb-2">
                                {failuresLoading && failures.length === 0 ? (
                                    <div className="py-3 text-center text-[10px]" style={{ color: 'var(--text-tertiary)' }}>
                                        <Spinner /> Loading...
                                    </div>
                                ) : failures.length === 0 ? (
                                    <div className="italic text-[10px] py-1.5" style={{ color: 'var(--text-tertiary)' }}>No failure records found for this job.</div>
                                ) : (
                                    <>
                                        <table className="w-full text-[10px] font-mono" style={{ borderCollapse: 'separate', borderSpacing: '0 1px' }}>
                                            <thead>
                                                <tr className="text-[8px] uppercase tracking-wider" style={{ color: 'var(--text-tertiary)' }}>
                                                    <th className="text-left px-1.5 py-0.5 font-bold">Service ID</th>
                                                    <th className="text-left px-1.5 py-0.5 font-bold">Type</th>
                                                    <th className="text-left px-1.5 py-0.5 font-bold">Detail</th>
                                                    <th className="text-right px-1.5 py-0.5 font-bold">Time</th>
                                                </tr>
                                            </thead>
                                            <tbody>
                                                {failures.map((f) => (
                                                    <tr key={f.id} style={{ background: 'var(--bg-hover)' }}>
                                                        <td className="px-1.5 py-1 select-all" style={{ color: 'var(--text-primary)' }}>{f.service_id}</td>
                                                        <td className="px-1.5 py-1">
                                                            <span
                                                                className="px-1 py-px rounded text-[8px] uppercase font-semibold"
                                                                style={f.action === 'error'
                                                                    ? { background: 'color-mix(in srgb, var(--danger) 10%, transparent)', color: 'var(--danger)' }
                                                                    : { background: 'color-mix(in srgb, var(--warning) 10%, transparent)', color: 'var(--warning)' }
                                                                }
                                                            >
                                                                {f.action}
                                                            </span>
                                                        </td>
                                                        <td className="px-1.5 py-1 break-all" style={{ color: 'var(--text-tertiary)', maxWidth: '280px' }}>{f.detail || '—'}</td>
                                                        <td className="px-1.5 py-1 text-right whitespace-nowrap" style={{ color: 'var(--text-tertiary)' }}>
                                                            {f.created_at ? format(new Date(f.created_at), "HH:mm:ss") : '—'}
                                                        </td>
                                                    </tr>
                                                ))}
                                            </tbody>
                                        </table>
                                        {failures.length < failuresTotal && (
                                            <div className="text-center pt-2">
                                                <button
                                                    onClick={handleLoadMoreFailures}
                                                    disabled={failuresLoading}
                                                    className="text-[9px] px-2 py-0.5 rounded transition-colors"
                                                    style={{ background: 'var(--bg-hover)', border: '1px solid var(--border)', color: 'var(--text-secondary)' }}
                                                >
                                                    {failuresLoading ? 'Loading...' : `Load More (${failures.length} / ${failuresTotal})`}
                                                </button>
                                            </div>
                                        )}
                                    </>
                                )}
                            </div>
                        </div>
                    )}

                </div>
            ) : metrics && (
                <div className="grid grid-cols-2 lg:grid-cols-4 gap-2 lg:gap-4 p-2 lg:p-4 shrink-0" style={{ background: 'var(--bg-card)', borderBottom: '1px solid var(--border)' }}>
                    <div className="p-2 rounded flex justify-between items-center" style={{ background: 'var(--bg-hover)', border: '1px solid var(--border)' }}>
                        <div>
                            <div className="text-[9px] uppercase font-bold" style={{ color: 'var(--text-tertiary)' }}>Users</div>
                            <div className="text-lg font-bold leading-none" style={{ color: 'var(--text-primary)' }}>{(metrics.users_inserted || 0) + (metrics.users_updated || 0)}</div>
                        </div>
                        <div className="text-[9px] text-right" style={{ color: 'var(--text-tertiary)' }}>
                            <div>+{metrics.users_inserted || 0}</div>
                            <div>~{metrics.users_updated || 0}</div>
                        </div>
                    </div>
                    <div className="p-2 rounded flex justify-between items-center" style={{ background: 'var(--bg-hover)', border: '1px solid var(--border)' }}>
                        <div>
                            <div className="text-[9px] uppercase font-bold" style={{ color: 'var(--text-tertiary)' }}>Groups</div>
                            <div className="text-lg font-bold leading-none" style={{ color: 'var(--text-primary)' }}>{(metrics.groups_inserted || 0) + (metrics.groups_updated || 0)}</div>
                        </div>
                        <div className="text-[9px] text-right" style={{ color: 'var(--text-tertiary)' }}>
                            <div>+{metrics.groups_inserted || 0}</div>
                            <div>~{metrics.groups_updated || 0}</div>
                        </div>
                    </div>
                    <div className="p-2 rounded flex justify-between items-center" style={{ background: 'var(--bg-hover)', border: '1px solid var(--border)' }}>
                        <div>
                            <div className="text-[9px] uppercase font-bold" style={{ color: 'var(--text-tertiary)' }}>Avatars</div>
                            <div className="text-lg font-bold leading-none" style={{ color: 'var(--text-primary)' }}>{(metrics.avatars_inserted || 0) + (metrics.avatars_updated || 0)}</div>
                        </div>
                        <div className="text-[9px] text-right" style={{ color: 'var(--text-tertiary)' }}>
                            <div>+{metrics.avatars_inserted || 0}</div>
                            <div>~{metrics.avatars_updated || 0}</div>
                        </div>
                    </div>
                </div>
            )}

            {/* Content */}
            {isMobile ? (
                /* ── Mobile: natural flow layout ── */
                <div className="flex flex-col">
                    {/* Task Progress — flows naturally */}
                    <div style={{ borderBottom: '1px solid var(--border)', background: 'var(--bg-card)' }}>
                        <div className="p-2 text-xs font-bold uppercase tracking-widest flex items-center gap-2" style={{ background: 'var(--bg-hover)', borderBottom: '1px solid var(--border)', color: 'var(--text-secondary)' }}>
                            <PiArticleBold className="text-lg" /> Task Progress
                        </div>
                        <div className="p-4">
                            <div className="space-y-0">
                                {steps.map((step, index) => (
                                    <JobStep key={step.id} step={step} isLast={index === steps.length - 1} logs={logs} />
                                ))}
                            </div>
                        </div>
                    </div>

                    {/* Logs access button — opens bottom sheet */}
                    <div className="p-3" style={{ background: 'var(--bg-card)' }}>
                        <button
                            onClick={() => setShowLogSheet(true)}
                            className="w-full flex items-center justify-between p-3 rounded-xl"
                            style={{ background: 'var(--bg-hover)', border: '1px solid var(--border)' }}
                        >
                            <span className="flex items-center gap-2 text-sm font-bold" style={{ color: 'var(--text-primary)' }}>
                                <PiTerminalWindowBold className="text-base" /> Live Logs ({logs.length})
                            </span>
                            <div className="flex items-center gap-2">
                                {errorLogs.length > 0 && (
                                    <span className="px-1.5 py-0.5 rounded text-[9px] font-bold" style={{ background: 'var(--danger-bg)', color: 'var(--danger)', border: '1px solid var(--danger)' }}>
                                        {errorLogs.length} ERR
                                    </span>
                                )}
                                <PiCaretDownBold className="text-xs" style={{ color: 'var(--text-tertiary)' }} />
                            </div>
                        </button>
                    </div>

                    {/* Log bottom sheet overlay */}
                    {showLogSheet && (
                        <>
                            <div onClick={() => setShowLogSheet(false)} style={{ position: 'fixed', inset: 0, zIndex: 80, background: 'rgba(0,0,0,0.5)' }} />
                            <div style={{
                                position: 'fixed', bottom: 0, left: 0, right: 0, zIndex: 90,
                                background: 'var(--bg-card)',
                                borderRadius: '16px 16px 0 0',
                                borderTop: '1px solid var(--border)',
                                height: '75vh',
                                display: 'flex', flexDirection: 'column',
                            }}>
                                <div style={{ width: 36, height: 4, background: 'var(--border)', borderRadius: 2, margin: '12px auto 4px', flexShrink: 0 }} />
                                <div className="px-4 py-2 flex items-center justify-between shrink-0" style={{ borderBottom: '1px solid var(--border)' }}>
                                    <span className="flex items-center gap-2 text-xs font-bold uppercase tracking-widest" style={{ color: 'var(--text-secondary)' }}>
                                        <PiTerminalWindowBold /> Logs ({logs.length})
                                        {errorLogs.length > 0 && (
                                            <span className="px-1 py-0.5 rounded text-[9px] font-bold" style={{ background: 'var(--danger-bg)', color: 'var(--danger)', border: '1px solid var(--danger)' }}>
                                                {errorLogs.length} ERR
                                            </span>
                                        )}
                                    </span>
                                    <div className="flex items-center gap-2">
                                        <select
                                            className="rounded px-1.5 py-0.5 focus:outline-none"
                                            style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', color: 'var(--text-secondary)', fontSize: '10px' }}
                                            value={logFilter}
                                            onChange={(e) => setLogFilter(e.target.value)}
                                        >
                                            <option value="ALL">All Levels</option>
                                            <option value="INFO">INFO</option>
                                            <option value="WARNING">WARNING</option>
                                            <option value="ERROR">ERROR</option>
                                        </select>
                                        <button onClick={handleDownloadLogs} className="si-icon-button" style={{ width: 28, height: 28 }}>
                                            <PiDownloadSimpleBold className="text-xs" />
                                        </button>
                                        <button onClick={() => setShowLogSheet(false)} className="si-icon-button" style={{ width: 28, height: 28 }}>
                                            <PiXBold className="text-xs" />
                                        </button>
                                    </div>
                                </div>
                                <div
                                    className="flex-1 overflow-y-auto custom-scrollbar p-3 font-mono text-xs"
                                    ref={logContainerRef}
                                    onScroll={handleScroll}
                                >
                                    {isLoadingMore && (
                                        <div className="text-center py-2" style={{ color: 'var(--text-tertiary)' }}>
                                            <Spinner /> Loading older logs...
                                        </div>
                                    )}
                                    {!hasMoreLogs && logs.length > 0 && (
                                        <div className="text-center py-2 text-[10px]" style={{ color: 'var(--text-tertiary)' }}>-- Start of Logs --</div>
                                    )}
                                    {filteredLogs.length === 0 && !isLoadingMore && (
                                        <span className="italic" style={{ color: 'var(--text-tertiary)' }}>
                                            {logFilter !== "ALL" && logs.length > 0
                                                ? `No ${logFilter} logs found.`
                                                : !["completed", "failed", "rolled_back"].includes(status)
                                                    ? "Waiting for logs..."
                                                    : "No logs found."}
                                        </span>
                                    )}
                                    {filteredLogs.map((log, i) => (
                                        <div key={i} className="mb-0.5 flex gap-2 hover:bg-white/5 px-1 -mx-1 rounded leading-5">
                                            <span className="w-[42px] flex-shrink-0 font-bold uppercase select-none text-right" style={{ color: log.log_level === "ERROR" ? 'var(--danger)' : log.log_level === "WARNING" ? 'var(--warning)' : 'var(--success)' }}>
                                                {log.log_level}
                                            </span>
                                            <span className="flex-1 min-w-0 break-words" style={{ color: 'var(--text-primary)', wordBreak: 'break-word' }}>
                                                {log.message}
                                            </span>
                                        </div>
                                    ))}
                                    <div ref={logEndRef} />
                                </div>
                            </div>
                        </>
                    )}
                </div>
            ) : (
                /* ── Desktop: fixed two-column layout with internal scroll ── */
                <div className="flex-1 flex flex-row overflow-hidden">
                    {/* Task Progress */}
                    <div className="w-1/2 h-full flex flex-col min-h-0" style={{ borderRight: '1px solid var(--border)', background: 'var(--bg-card)' }}>
                        <div className="p-2 text-xs font-bold uppercase tracking-widest flex items-center gap-2" style={{ background: 'var(--bg-hover)', borderBottom: '1px solid var(--border)', color: 'var(--text-secondary)' }}>
                            <PiArticleBold className="text-lg" /> Task Progress
                        </div>
                        <div className="flex-1 overflow-y-auto custom-scrollbar p-4 md:p-6">
                            <div className="space-y-0">
                                {steps.map((step, index) => (
                                    <JobStep key={step.id} step={step} isLast={index === steps.length - 1} logs={logs} />
                                ))}
                            </div>
                        </div>
                    </div>

                    {/* Logs — desktop side panel */}
                    <div className="w-1/2 h-full flex flex-col min-h-0" style={{ background: 'var(--bg-card)' }}>
                        <div className="w-full p-2 border-b text-xs font-bold uppercase tracking-widest flex justify-between items-center" style={{ background: 'var(--bg-hover)', borderBottomColor: 'var(--border)', color: 'var(--text-secondary)' }}>
                            <span className="flex items-center gap-2">
                                <PiTerminalWindowBold className="text-lg" />
                                Live Logs ({logs.length})
                            </span>
                            <div className="flex items-center gap-2">
                                <button onClick={handleDownloadLogs} title="Download Logs" className="p-1" style={{ color: 'var(--text-secondary)' }}
                                    onMouseEnter={(e) => e.currentTarget.style.color = 'var(--text-primary)'}
                                    onMouseLeave={(e) => e.currentTarget.style.color = 'var(--text-secondary)'}
                                >
                                    <PiDownloadSimpleBold />
                                </button>
                                <select
                                    className="rounded px-1.5 py-0.5 focus:outline-none"
                                    style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', color: 'var(--text-secondary)', fontSize: '10px' }}
                                    value={logFilter}
                                    onChange={(e) => setLogFilter(e.target.value)}
                                >
                                    <option value="ALL">All Levels</option>
                                    <option value="INFO">INFO</option>
                                    <option value="WARNING">WARNING</option>
                                    <option value="ERROR">ERROR</option>
                                </select>
                                <button
                                    onClick={() => setAutoScroll(!autoScroll)}
                                    className="text-[10px] px-2 py-0.5 rounded-full transition-colors"
                                    style={autoScroll ? { background: 'var(--success-bg)', color: 'var(--success)', fontSize: '10px' } : { background: 'var(--bg-hover)', color: 'var(--text-secondary)', fontSize: '10px' }}
                                >
                                    {autoScroll ? "Auto-scroll ON" : "Auto-scroll OFF"}
                                </button>
                            </div>
                        </div>
                        <div
                            className="flex-1 overflow-y-auto custom-scrollbar p-4 font-mono text-xs"
                            ref={logContainerRef}
                            onScroll={handleScroll}
                        >
                            {isLoadingMore && (
                                <div className="text-center py-2" style={{ color: 'var(--text-tertiary)' }}>
                                    <Spinner /> Loading older logs...
                                </div>
                            )}
                            {!hasMoreLogs && logs.length > 0 && (
                                <div className="text-center py-2 text-[10px]" style={{ color: 'var(--text-tertiary)' }}>-- Start of Logs --</div>
                            )}
                            {filteredLogs.length === 0 && !isLoadingMore && (
                                <span className="italic" style={{ color: 'var(--text-tertiary)' }}>
                                    {logFilter !== "ALL" && logs.length > 0
                                        ? `No ${logFilter} logs found.`
                                        : !["completed", "failed", "rolled_back"].includes(status)
                                            ? "Waiting for logs..."
                                            : "No logs found."}
                                </span>
                            )}
                            {filteredLogs.map((log, i) => (
                                <div key={i} className="mb-0.5 flex gap-2 hover:bg-white/5 px-1 -mx-1 rounded leading-5">
                                    <span className="w-[58px] flex-shrink-0 select-none tabular-nums" style={{ color: 'var(--text-tertiary)' }}>
                                        {format(new Date(log.timestamp), "HH:mm:ss")}
                                    </span>
                                    <span className="w-[42px] flex-shrink-0 font-bold uppercase select-none text-right" style={{ color: log.log_level === "ERROR" ? 'var(--danger)' : log.log_level === "WARNING" ? 'var(--warning)' : 'var(--success)' }}>
                                        {log.log_level}
                                    </span>
                                    <span className="flex-1 min-w-0 break-words" style={{ color: 'var(--text-primary)', wordBreak: 'break-word' }}>
                                        {log.message}
                                    </span>
                                </div>
                            ))}
                            <div ref={logEndRef} />
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};


export const UploadPanel = ({ onJobStarted, config }) => {
    const [activeTab, setActiveTab] = useState("file");
    const [files, setFiles] = useState(null);
    const [error, setError] = useState("");
    const [uploading, setUploading] = useState(false);
    const [uploadProgress, setUploadProgress] = useState(0);
    const abortRef = useRef(false);
    const currentUploadIdRef = useRef(null);

    const handleFileChange = (e) => {
        setFiles(e.target.files);
        setError("");
        setUploadProgress(0);
    };

    const handleUpload = async () => {
        setUploading(true);
        setError("");
        setUploadProgress(0);
        abortRef.current = false;
        currentUploadIdRef.current = null;

        try {
            const endpoint = config.endpoints.uploadFile;
            if (!endpoint) throw new Error("Endpoint not configured");

            let finalPayload = {};
            let finalHeaders = {};
            // Default 5MB chunks
            const CHUNK_SIZE = 1 * 1024 * 1024;

            if (config.chunked && files && files[0].size > CHUNK_SIZE) {
                const file = files[0];
                const totalChunks = Math.ceil(file.size / CHUNK_SIZE);

                // 1. Init Upload
                const initRes = await apiClient.post("/uploads/init", {
                    filename: file.name,
                    total_chunks: totalChunks
                });
                const uploadId = initRes.data.upload_id;
                currentUploadIdRef.current = uploadId;

                // 2. Upload Chunks
                for (let i = 0; i < totalChunks; i++) {
                    const start = i * CHUNK_SIZE;
                    const end = Math.min(start + CHUNK_SIZE, file.size);
                    const chunk = file.slice(start, end);

                    const formData = new FormData();
                    formData.append("chunk_index", i);
                    formData.append("file", chunk);

                    await apiClient.post(`/uploads/${uploadId}/chunk`, formData, {
                        headers: { "Content-Type": "multipart/form-data" }
                    });

                    if (abortRef.current) {
                        try {
                            await apiClient.delete(`/uploads/${uploadId}/abort`);
                        } catch (e) {
                            console.error("Failed to call abort on backend", e);
                        }
                        throw new Error("Upload aborted by user");
                    }

                    // Update Progress (90% allocated for upload)
                    const percent = Math.round(((i + 1) / totalChunks) * 90);
                    setUploadProgress(percent);
                }

                // 3. Complete Upload
                await apiClient.post(`/uploads/${uploadId}/complete`, {
                    filename: file.name
                });

                finalPayload = { upload_id: uploadId };
                finalHeaders = { "Content-Type": "application/json" };
            }
            else if (config.sendJson && files) {
                // 1. Upload File (Single Request)
                const uploadFormData = new FormData();
                uploadFormData.append("file", files[0]);

                const uploadRes = await apiClient.post("/upload/file", uploadFormData, {
                    headers: { "Content-Type": "multipart/form-data" },
                    onUploadProgress: (p) => setUploadProgress(Math.round((p.loaded * 100) / p.total * 0.9))
                });

                finalPayload = { upload_id: uploadRes.data.upload_id };
                finalHeaders = { "Content-Type": "application/json" };
            } else {
                if (files) {
                    const formData = new FormData();
                    formData.append("file", files[0]);
                    finalPayload = formData;
                    finalHeaders = { "Content-Type": "multipart/form-data" };
                }
            }

            const triggerRes = await apiClient.post(endpoint, finalPayload, { headers: finalHeaders });

            setUploadProgress(100);
            if (triggerRes.data.job_id) {
                onJobStarted(triggerRes.data.job_id);
            }

        } catch (err) {
            console.error(err);
            setError(err.response?.data?.detail || err.message || "Upload failed");
        } finally {
            setUploading(false);
            currentUploadIdRef.current = null;
        }
    };

    const handleAbort = () => {
        abortRef.current = true;
    };

    const resetState = () => {
        setError("");
        setFiles(null);
    };

    return (
        <div className="rounded-xl p-4 md:p-6 max-w-xl mx-auto animate-fade-in-up" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
            <div className="text-center mb-6">
                <h2 className="text-xl font-bold mb-1" style={{ color: 'var(--text-primary)' }}>{config.title}</h2>
                <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>{config.description}</p>
            </div>

            <div className="flex p-1 rounded-lg mb-6" style={{ background: 'var(--bg-hover)', border: '1px solid var(--border)' }}>
                <button
                    onClick={() => { setActiveTab("file"); resetState(); }}
                    className={`flex-1 flex items-center justify-center gap-2 py-2 rounded-md transition-all text-xs font-bold ${activeTab === "file"
                        ? "si-button-primary shadow-lg"
                        : ""
                        }`}
                    style={activeTab !== "file" ? { color: 'var(--text-secondary)' } : undefined}
                >
                    <PiFolderOpenBold /> {config.fileLabel || "Upload File(s)"}
                </button>
            </div>

            <div className="rounded-xl text-center transition-all group" style={{ border: '1px dashed var(--border)', background: 'var(--bg-hover)' }}
                onMouseEnter={(e) => { e.currentTarget.style.borderColor = 'var(--accent)'; }}
                onMouseLeave={(e) => { e.currentTarget.style.borderColor = 'var(--border)'; }}
            >
                <input
                    type="file"
                    id="file-upload"
                    accept={config.accept}
                    className="hidden"
                    onChange={handleFileChange}
                />
                <label
                    htmlFor="file-upload"
                    className="cursor-pointer flex flex-col items-center p-6"
                >
                    <div className="w-12 h-12 rounded-full flex items-center justify-center mb-3 group-hover:scale-110 transition-transform shadow-lg"
                        style={{ background: 'var(--bg-hover)', border: '1px solid var(--border)' }}>
                        <PiFolderOpenBold className="w-6 h-6" style={{ color: 'var(--accent)' }} />
                    </div>
                    <span className="text-sm font-bold mb-1 px-4 break-all" style={{ color: 'var(--text-primary)' }}>
                        {files
                            ? (files.length === 1
                                ? `${files[0].name} (${(files[0].size / 1024 / 1024).toFixed(2)} MB)`
                                : `${files.length} files selected`)
                            : (config.fileSelectLabel || "Select Files")}
                    </span>
                    <span className="text-[10px] font-mono" style={{ color: 'var(--text-tertiary)' }}>
                        {config.supportedFormats}
                    </span>
                </label>
            </div>

            {error && <p className="text-[10px] font-bold mt-4 text-center py-2 rounded" style={{ color: 'var(--danger)', background: 'var(--danger-bg)', border: '1px solid var(--danger)' }}>{error}</p>}

            <button
                onClick={handleUpload}
                disabled={uploading || !files}
                className="w-full mt-6 font-bold rounded-lg shadow-lg relative overflow-hidden transition-all text-sm"
                style={uploading
                    ? { background: 'var(--bg-hover)', color: 'var(--text-primary)', cursor: 'wait' }
                    : (!files
                        ? { background: 'var(--bg-hover)', color: 'var(--text-tertiary)', cursor: 'not-allowed' }
                        : { background: 'var(--accent)', color: 'var(--text-primary)' })}
            >
                {uploading && (
                    <div
                        className="absolute left-0 top-0 bottom-0 transition-all duration-300 ease-out"
                        style={{ width: `${uploadProgress}%`, background: 'var(--accent)', opacity: 0.8 }}
                    />
                )}
                <div className="relative z-10 flex items-center justify-center gap-2 py-2.5">
                    {uploading ? (
                        <>
                            <Spinner /> <span className="animate-pulse drop-shadow-md">Uploading... {uploadProgress}%</span>
                        </>
                    ) : (
                        <>
                            <PiCloudArrowUpBold className="text-lg" /> Start Ingestion
                        </>
                    )}
                </div>
            </button>

            {uploading && (
                <button
                    onClick={handleAbort}
                    className="w-full mt-2 py-2 text-xs font-bold rounded-lg transition-all flex items-center justify-center gap-2"
                    style={{ color: 'var(--danger)', border: '1px solid var(--danger)' }}
                >
                    <PiXBold /> Abort Upload
                </button>
            )}
        </div>
    );
};


export const UserDetailModal = ({ user, onClose }) => {
    const [fullUser, setFullUser] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        if (!user?.id) return;
        const fetchUser = async () => {
            try {
                const { data } = await apiClient.get(`/app-users/${user.id}`);
                setFullUser(data);
            } catch (e) {
                console.error("Failed to fetch user details", e);
            } finally {
                setLoading(false);
            }
        };
        fetchUser();
    }, [user]);

    if (!user) return null;

    const displayUser = fullUser || user;

    return (
        <div className="fixed inset-0 z-[200] flex items-center justify-center bg-black/50 backdrop-blur-sm animate-fade-in p-4" onClick={onClose}>
            <div className="rounded-xl shadow-2xl w-full max-w-sm overflow-hidden animate-scale-in" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }} onClick={e => e.stopPropagation()}>
                <div className="h-24 relative" style={{ background: 'linear-gradient(to right, var(--accent), var(--accent))' }}>
                    <button onClick={onClose} className="absolute top-2 right-2 p-1.5 bg-black/20 hover:bg-black/40 rounded-full transition-colors" style={{ color: 'var(--text-primary)' }}>
                        <PiXBold />
                    </button>
                </div>
                <div className="px-6 pb-6 -mt-10 relative">
                    <div className="flex justify-between items-end mb-4">
                        <div className="w-20 h-20 rounded-2xl overflow-hidden shadow-lg flex items-center justify-center" style={{ border: '4px solid var(--bg-card)', background: 'var(--bg-hover)' }}>
                            <PiUserBold className="text-4xl" style={{ color: 'var(--text-tertiary)' }} />
                        </div>
                        <div className="px-2 py-1 rounded text-[10px] font-bold uppercase flex items-center gap-1"
                            style={displayUser.is_active
                                ? { background: 'var(--success-bg)', color: 'var(--success)', border: '1px solid var(--success)' }
                                : { background: 'var(--danger-bg)', color: 'var(--danger)', border: '1px solid var(--danger)' }}>
                            {displayUser.is_active ? <PiCheckBold /> : <PiXBold />} {displayUser.is_active ? "Active" : "Inactive"}
                        </div>
                    </div>

                    <h3 className="text-xl font-bold mb-0.5" style={{ color: 'var(--text-primary)' }}>{displayUser.email || "Unknown User"}</h3>

                    <div className="space-y-2 rounded-lg p-3" style={{ background: 'var(--bg-hover)', border: '1px solid var(--border)' }}>
                        <div className="flex justify-between items-center text-xs">
                            <span style={{ color: 'var(--text-tertiary)' }}>User ID</span>
                            <span className="font-mono" style={{ color: 'var(--text-primary)' }}>#{displayUser.id}</span>
                        </div>
                        <div className="flex justify-between items-center text-xs">
                            <span style={{ color: 'var(--text-tertiary)' }}>Role</span>
                            <span className="font-bold flex items-center gap-1" style={{ color: displayUser.is_superuser ? 'var(--warning)' : 'var(--text-primary)' }}>
                                {displayUser.is_superuser ? <><PiShieldCheckBold /> Super Admin</> : "User"}
                            </span>
                        </div>
                        {loading ? (
                            <div className="flex justify-center py-2"><Spinner /></div>
                        ) : (
                            <div className="flex justify-between items-center text-xs">
                                <span style={{ color: 'var(--text-tertiary)' }}>Last Login</span>
                                <span style={{ color: 'var(--text-primary)' }}>
                                    {fullUser?.last_login ? format(new Date(fullUser.last_login), "PP p") : "Never"}
                                </span>
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
};


export const JobsList = ({ onSelectJob, endpoints, selectedJobId, jobs, loading, onRefresh, onLoadMore, hasMore, className = "" }) => {
    const [selectedUser, setSelectedUser] = useState(null);

    return (
        <>
            <div className={`flex flex-col w-full md:w-80 flex-shrink-0 max-h-[250px] md:max-h-none md:min-h-0 ${className}`}
                style={{ background: 'var(--bg-card)', borderBottom: '1px solid var(--border)', borderRight: '1px solid var(--border)' }}>
                <div className="p-4 flex justify-between items-center flex-shrink-0" style={{ background: 'var(--bg-card)', borderBottom: '1px solid var(--border)' }}>
                    <h3 className="font-bold flex items-center gap-2 text-xs uppercase tracking-wider" style={{ color: 'var(--text-primary)' }}>
                        <PiClockCounterClockwiseBold /> Recent Jobs
                    </h3>
                    <div className="flex gap-2">
                        <button onClick={onRefresh} className="font-bold tracking-wider px-2 py-1"
                            style={{ color: 'var(--text-secondary)' }}
                            onMouseEnter={(e) => e.currentTarget.style.color = 'var(--text-primary)'}
                            onMouseLeave={(e) => e.currentTarget.style.color = 'var(--text-secondary)'}
                        >
                            Refresh
                        </button>
                    </div>
                </div>
                <div
                    className="flex-1 overflow-y-auto"
                    onScroll={(e) => {
                        const { scrollTop, scrollHeight, clientHeight } = e.currentTarget;
                        // Trigger when within 50px of bottom
                        if (scrollHeight - scrollTop <= clientHeight + 50 && hasMore && !loading) {
                            onLoadMore();
                        }
                    }}
                >
                    <div className="custom-scrollbar p-2 space-y-2 min-h-0 max-h-[100%]">
                        {loading && jobs.length === 0 && (
                            <div className="flex justify-center py-8"><Spinner /></div>
                        )}

                        {!loading && jobs.length === 0 && (
                            <div className="text-center py-8" style={{ color: 'var(--text-tertiary)' }}>
                                <PiClockCounterClockwiseBold className="text-2xl mx-auto mb-2 opacity-20" />
                                <p className="text-xs">No jobs found.</p>
                            </div>
                        )}

                        {jobs.map((job) => (
                            <div
                                key={job.id}
                                onClick={() => onSelectJob(job.id, job)}
                                className="p-3 rounded-lg cursor-pointer transition-all"
                                style={selectedJobId === job.id
                                    ? { background: 'color-mix(in srgb, var(--accent) 10%, transparent)', border: '1px solid var(--accent)', boxShadow: '0 0 10px color-mix(in srgb, var(--accent) 20%, transparent)' }
                                    : { background: 'var(--bg-hover)', border: '1px solid var(--border)' }}
                                onMouseEnter={(e) => { if (selectedJobId !== job.id) e.currentTarget.style.background = 'var(--bg-hover)'; }}
                                onMouseLeave={(e) => { if (selectedJobId !== job.id) e.currentTarget.style.background = 'var(--bg-hover)'; }}
                            >
                                <div className="flex justify-between items-start mb-2">
                                    <span className="text-xs font-mono font-bold" style={{ color: 'var(--text-primary)' }}>#{job.id}</span>
                                    <span className="px-1.5 py-0.5 rounded text-[10px] font-bold uppercase" style={{ ...getStatusStyle(job.status), borderWidth: '1px', borderStyle: 'solid' }}>
                                        {job.status}
                                    </span>
                                </div>

                                {job.created_by_user && (
                                    <div className="flex items-center gap-1.5 mt-2 mb-2 p-1 rounded" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
                                        <div className="text-[9px] uppercase tracking-wider font-bold ml-1" style={{ color: 'var(--text-tertiary)' }}>By</div>
                                        <button
                                            onClick={(e) => {
                                                e.stopPropagation();
                                                setSelectedUser(job.created_by_user);
                                            }}
                                            className="flex items-center gap-1.5 rounded px-1.5 py-0.5 transition-colors group"
                                            onMouseEnter={(e) => e.currentTarget.style.background = 'var(--bg-hover)'}
                                            onMouseLeave={(e) => e.currentTarget.style.background = ''}
                                        >
                                            <PiUserCircleBold className="w-3.5 h-3.5" style={{ color: 'var(--text-tertiary)' }} />
                                            <span className="text-[10px] font-medium truncate max-w-[100px]" style={{ color: 'var(--text-primary)' }}>
                                                {job.created_by_user.email}
                                            </span>
                                        </button>
                                    </div>
                                )}

                                <div className="flex justify-between items-end mt-1">
                                    <span className="text-[10px] font-mono truncate max-w-[120px]" style={{ color: 'var(--text-tertiary)' }} title={job.batch_info}>
                                        {job.ingestion_type}
                                    </span>
                                    <span className="text-[10px] font-mono" style={{ color: 'var(--text-tertiary)' }}>
                                        {job.created_at ? format(new Date(job.created_at), "MMM d, HH:mm") : "-"}
                                    </span>
                                </div>
                            </div>
                        ))}

                        {hasMore && (
                            <button
                                onClick={onLoadMore}
                                disabled={loading}
                                className="w-full py-2 text-xs font-bold rounded transition-all flex justify-center items-center gap-2"
                                style={{ color: 'var(--text-tertiary)', border: '1px solid transparent' }}
                                onMouseEnter={(e) => { e.currentTarget.style.color = 'var(--text-primary)'; e.currentTarget.style.background = 'var(--bg-hover)'; e.currentTarget.style.borderColor = 'var(--border)'; }}
                                onMouseLeave={(e) => { e.currentTarget.style.color = 'var(--text-tertiary)'; e.currentTarget.style.background = ''; e.currentTarget.style.borderColor = 'transparent'; }}
                            >
                                {loading && jobs.length > 0 ? <Spinner /> : <PiArrowCounterClockwiseBold />}
                                Load More
                            </button>
                        )}
                    </div>
                </div>
            </div>

            {selectedUser && (
                <UserDetailModal user={selectedUser} onClose={() => setSelectedUser(null)} />
            )}
        </>
    );
};

// ─── Mobile Job Picker ───────────────────────────────────────────────────────

const JobPickerItem = ({ job, selected, onSelect }) => {
    const ss = getStatusStyle(job.status);
    return (
        <button
            onClick={() => onSelect(job.id, job)}
            style={{
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                width: '100%', padding: '10px 12px', borderRadius: 10, marginBottom: 6,
                background: selected ? 'color-mix(in srgb, var(--accent) 10%, transparent)' : 'var(--bg-hover)',
                border: `1px solid ${selected ? 'var(--accent)' : 'var(--border)'}`,
                textAlign: 'left', cursor: 'pointer',
            }}
        >
            <div style={{ minWidth: 0 }}>
                <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 2 }}>
                    Job #{job.id}
                </div>
                <div style={{ fontSize: 11, color: 'var(--text-tertiary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {job.ingestion_type}{job.created_at ? ` · ${format(new Date(job.created_at), "MMM d, HH:mm")}` : ''}
                </div>
            </div>
            <span style={{ ...ss, borderWidth: '1px', borderStyle: 'solid', borderRadius: 4, padding: '2px 7px', fontSize: 10, fontWeight: 700, textTransform: 'uppercase', flexShrink: 0, marginLeft: 8 }}>
                {job.status}
            </span>
        </button>
    );
};

const MobileJobPicker = ({ jobs, selectedJobId, onSelect, onClose, loading, onRefresh }) => {
    const [search, setSearch] = useState("");

    const filtered = useMemo(() => {
        const q = search.trim().toLowerCase();
        if (!q) return jobs;
        return jobs.filter(j =>
            String(j.id).includes(q) ||
            j.status?.toLowerCase().includes(q) ||
            j.ingestion_type?.toLowerCase().includes(q) ||
            (j.created_at && format(new Date(j.created_at), "MMM d HH:mm").toLowerCase().includes(q))
        );
    }, [jobs, search]);

    const recent = filtered.slice(0, 5);
    const earlier = filtered.slice(5);

    const handleSelect = (id, job) => { onSelect(id, job); onClose(); };

    return (
        <>
            <div onClick={onClose} style={{ position: 'fixed', inset: 0, zIndex: 80, background: 'rgba(0,0,0,0.5)' }} />
            <div style={{
                position: 'fixed', bottom: 60, left: 0, right: 0, zIndex: 90,
                background: 'var(--bg-card)', borderRadius: '16px 16px 0 0',
                borderTop: '1px solid var(--border)', maxHeight: '72vh',
                display: 'flex', flexDirection: 'column',
            }}>
                {/* Handle */}
                <div style={{ width: 36, height: 4, background: 'var(--border)', borderRadius: 2, margin: '12px auto 0', flexShrink: 0 }} />

                {/* Header */}
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 16px 8px', flexShrink: 0 }}>
                    <span style={{ fontWeight: 700, fontSize: 14, color: 'var(--text-primary)' }}>Select Job</span>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <button onClick={onRefresh} style={{ fontSize: 12, color: 'var(--accent)', fontWeight: 600 }}>Refresh</button>
                        <button onClick={onClose} className="si-icon-button" style={{ width: 28, height: 28 }}>
                            <PiXBold className="text-xs" />
                        </button>
                    </div>
                </div>

                {/* Search */}
                <div style={{ padding: '0 16px 10px', flexShrink: 0 }}>
                    <input
                        type="text"
                        value={search}
                        onChange={e => setSearch(e.target.value)}
                        placeholder="Search by ID, status, type..."
                        className="si-input w-full"
                        style={{ fontSize: 13 }}
                        autoFocus
                    />
                </div>

                {/* Job list */}
                <div style={{ flex: 1, overflowY: 'auto', padding: '0 16px 16px' }}>
                    {loading && jobs.length === 0 ? (
                        <div style={{ textAlign: 'center', padding: 24, color: 'var(--text-tertiary)' }}><Spinner /></div>
                    ) : filtered.length === 0 ? (
                        <div style={{ textAlign: 'center', padding: 24, color: 'var(--text-tertiary)', fontSize: 13 }}>
                            No jobs match "{search}"
                        </div>
                    ) : (
                        <>
                            {recent.length > 0 && (
                                <>
                                    <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 8 }}>
                                        Recent
                                    </div>
                                    {recent.map(job => <JobPickerItem key={job.id} job={job} selected={job.id === selectedJobId} onSelect={handleSelect} />)}
                                </>
                            )}
                            {earlier.length > 0 && (
                                <>
                                    <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.08em', margin: '12px 0 8px' }}>
                                        Earlier
                                    </div>
                                    {earlier.map(job => <JobPickerItem key={job.id} job={job} selected={job.id === selectedJobId} onSelect={handleSelect} />)}
                                </>
                            )}
                        </>
                    )}
                </div>
            </div>
        </>
    );
};

// ─── Generic Ingestion Layout ─────────────────────────────────────────────────

export const GenericIngestionLayout = ({ config, endpoints, currentJobId, onSelectJob, onJobStarted, children }) => {
    const isMobile = useIsMobile();
    const [jobs, setJobs] = useState([]);
    const [loading, setLoading] = useState(true);
    const [offset, setOffset] = useState(0);
    const [hasMore, setHasMore] = useState(true);
    const [showJobPicker, setShowJobPicker] = useState(false);
    const [mobileView, setMobileView] = useState('list'); // 'list' | 'detail' | 'create'
    const hasAutoSelected = useRef(false);
    const LIMIT = 20;

    const fetchJobs = async (isRefresh = false, pageOffset = 0) => {
        if (loading && !isRefresh) return;
        setLoading(true);
        try {
            const { data } = await apiClient.get(endpoints.jobs, { params: { limit: LIMIT, offset: pageOffset } });
            const items = data.items || [];
            const total = data.total || 0;

            if (isRefresh || pageOffset === 0) {
                if (offset > 0 && !isRefresh && pageOffset === 0) {
                    setJobs(prev => {
                        const merged = [...items, ...prev.slice(items.length)];
                        return merged;
                    });
                } else {
                    setJobs(items);
                    setOffset(items.length);
                    setHasMore(items.length < total);
                }
            } else {
                if (items.length > 0) {
                    setJobs(prev => [...prev, ...items]);
                    setOffset(prev => prev + items.length);
                }
                setHasMore(jobs.length + items.length < total);
            }
        } catch (err) {
            console.error("Error fetching jobs:", err);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        let isMounted = true;
        let timeoutId;

        fetchJobs(true, 0);

        const pollJobs = async () => {
            if (!isMounted) return;
            try {
                const { data } = await apiClient.get(endpoints.jobs, { params: { limit: LIMIT, offset: 0 } });
                const items = data.items || [];
                if (isMounted) {
                    setJobs(prev => {
                        if (prev.length <= LIMIT) return items;
                        return [...items, ...prev.slice(items.length)];
                    });
                }
            } catch (e) { }

            if (isMounted) {
                timeoutId = setTimeout(pollJobs, 4000);
            }
        };

        timeoutId = setTimeout(pollJobs, 4000);

        return () => {
            isMounted = false;
            if (timeoutId) clearTimeout(timeoutId);
        };
    }, [endpoints.jobs]);

    const selectedJob = useMemo(() => {
        return jobs.find(j => j.id === currentJobId) || null;
    }, [jobs, currentJobId]);

    const handleRefresh = () => { setOffset(0); setHasMore(true); fetchJobs(true, 0); };

    // Auto-switch to detail when currentJobId set externally on mobile (e.g. AvatarSync trigger)
    useEffect(() => {
        if (isMobile && currentJobId) {
            setMobileView('detail');
        }
    }, [isMobile, currentJobId]);

    // Mobile job selection: switch to detail view
    const handleMobileSelectJob = (jobId, job) => {
        onSelectJob(jobId, job);
        setMobileView('detail');
    };

    // Mobile back: return to list
    const handleMobileBack = () => {
        onSelectJob(null);
        setMobileView('list');
    };

    // Mobile new job started: switch to detail view
    const handleMobileJobStarted = (jobId) => {
        onJobStarted(jobId);
        setMobileView('detail');
    };

    if (isMobile) {
        // --- MOBILE: 3 exclusive states ---

        // STATE 1: JOB LIST
        if (mobileView === 'list') {
            return (
                <div className="flex flex-col animate-fade-in">
                    {/* Header bar */}
                    <div className="flex items-center justify-between px-4 py-3 mb-3 rounded-xl"
                        style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
                        <div>
                            <h2 className="text-base font-bold" style={{ color: 'var(--text-primary)' }}>
                                {config?.title || 'Recent Jobs'}
                            </h2>
                            <p className="text-xs mt-0.5" style={{ color: 'var(--text-tertiary)' }}>
                                {jobs.length} job{jobs.length !== 1 ? 's' : ''}
                            </p>
                        </div>
                        <button
                            onClick={() => setMobileView('create')}
                            className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-semibold"
                            style={{ background: 'var(--accent)', color: '#fff' }}
                        >
                            {children ? <PiArticleBold /> : <PiCloudArrowUpBold />}
                            {children ? 'Configuration' : 'New'}
                        </button>
                    </div>

                    {/* Jobs list — full page, no scroll jail */}
                    {loading && jobs.length === 0 && (
                        <div className="flex justify-center py-12"><Spinner /></div>
                    )}
                    {!loading && jobs.length === 0 && (
                        <div className="text-center py-12" style={{ color: 'var(--text-tertiary)' }}>
                            <PiClockCounterClockwiseBold className="text-3xl mx-auto mb-3 opacity-20" />
                            <p className="text-sm font-medium">No jobs yet</p>
                            <p className="text-xs mt-1">Start your first ingestion job</p>
                        </div>
                    )}
                    <div className="space-y-2">
                        {jobs.map((job) => (
                            <div
                                key={job.id}
                                onClick={() => handleMobileSelectJob(job.id, job)}
                                className="p-4 rounded-xl cursor-pointer"
                                style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}
                            >
                                <div className="flex justify-between items-center mb-1">
                                    <span className="text-sm font-mono font-bold" style={{ color: 'var(--text-primary)' }}>
                                        Job #{job.id}
                                    </span>
                                    <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase"
                                        style={{ ...getStatusStyle(job.status), borderWidth: '1px', borderStyle: 'solid' }}>
                                        {job.status}
                                    </span>
                                </div>
                                {job.created_at && (
                                    <p className="text-xs" style={{ color: 'var(--text-tertiary)' }}>
                                        {format(new Date(job.created_at), "MMM d, yyyy · HH:mm")}
                                    </p>
                                )}
                                {job.created_by_user && (
                                    <p className="text-xs mt-1" style={{ color: 'var(--text-secondary)' }}>
                                        {job.created_by_user.email}
                                    </p>
                                )}
                            </div>
                        ))}
                        {hasMore && (
                            <button
                                onClick={() => fetchJobs(false, offset)}
                                className="w-full py-3 text-sm font-medium rounded-xl"
                                style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', color: 'var(--accent)' }}
                            >
                                Load more
                            </button>
                        )}
                    </div>
                </div>
            );
        }

        // STATE 2: JOB DETAIL
        if (mobileView === 'detail') {
            return (
                <div className="flex flex-col animate-fade-in">
                    <JobMonitor
                        job={selectedJob}
                        jobId={currentJobId}
                        endpoints={endpoints}
                        onNewJob={() => { onSelectJob(null); setMobileView('create'); }}
                        onBack={handleMobileBack}
                        onSwitchJob={handleMobileSelectJob}
                        onOpenPicker={undefined}
                    />
                </div>
            );
        }

        // STATE 3: CREATE
        return (
            <div className="flex flex-col animate-fade-in">
                {/* Back header */}
                <div className="flex items-center gap-3 px-1 py-3 mb-4">
                    <button
                        onClick={() => setMobileView('list')}
                        className="flex items-center gap-1.5 text-sm font-medium"
                        style={{ color: 'var(--accent)' }}
                    >
                        <PiArrowLeftBold />
                        Jobs
                    </button>
                    <span className="text-sm font-bold" style={{ color: 'var(--text-primary)' }}>
                        {children ? 'Configuration' : (config?.title || 'New Ingestion')}
                    </span>
                </div>

                {children ? children : (
                    <div className="flex flex-col items-center animate-fade-in">
                        <div className="w-full">
                            <UploadPanel onJobStarted={handleMobileJobStarted} config={config} />
                        </div>
                    </div>
                )}
            </div>
        );
    }

    // --- DESKTOP: unchanged layout ---
    return (
        <div className="flex flex-col md:flex-row rounded-lg mb-6 md:min-h-[500px] md:max-h-[800px] overflow-hidden"
            style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
            <div className={currentJobId ? 'hidden md:flex' : 'flex'}>
                <JobsList
                    onSelectJob={onSelectJob}
                    endpoints={endpoints}
                    selectedJobId={currentJobId}
                    jobs={jobs}
                    loading={loading}
                    onRefresh={handleRefresh}
                    onLoadMore={() => fetchJobs(false, offset)}
                    hasMore={hasMore}
                />
            </div>

            <div className="flex-1 relative flex flex-col md:overflow-auto">
                {currentJobId ? (
                    <div className="h-full overflow-hidden flex flex-col">
                        <JobMonitor
                            job={selectedJob}
                            jobId={currentJobId}
                            endpoints={endpoints}
                            onNewJob={() => onSelectJob(null)}
                            onBack={() => onSelectJob(null)}
                            onSwitchJob={onSelectJob}
                            onOpenPicker={undefined}
                        />
                    </div>
                ) : (
                    children ? children : (
                        <div className="flex flex-col items-center p-4 md:p-6 animate-fade-in overflow-y-auto">
                            <div className="w-full max-w-xl">
                                <div className="text-center mb-4 md:mb-8">
                                    <h2 className="text-xl md:text-2xl font-bold mb-2" style={{ color: 'var(--text-primary)' }}>Ready to Ingest</h2>
                                    <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>Start a new ingestion job.</p>
                                </div>
                                <UploadPanel onJobStarted={onJobStarted} config={config} />
                            </div>
                        </div>
                    )
                )}
            </div>
        </div>
    );
};
