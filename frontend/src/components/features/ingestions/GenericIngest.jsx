import React, { useState, useEffect } from 'react';
import apiClient from '../../../services/api';
import LogViewer from './LogViewer';
import { FaUpload, FaSpinner, FaCheckCircle, FaExclamationCircle } from 'react-icons/fa';

export default function GenericIngest({ title, description, endpoint, fileAccept, fileLabel }) {
    const [file, setFile] = useState(null);
    const [uploading, setUploading] = useState(false);
    const [status, setStatus] = useState('idle'); // idle, uploading, processing, success, error
    const [message, setMessage] = useState('');
    const [jobId, setJobId] = useState(null);
    const [progress, setProgress] = useState(0);

    const handleFileChange = (e) => {
        if (e.target.files[0]) {
            setFile(e.target.files[0]);
        }
    };

    const handleUpload = async () => {
        if (!file) return;

        setUploading(true);
        setStatus('uploading');
        setMessage('Starting upload...');
        setJobId(null);
        setProgress(0);

        try {
            // Step 1: Init Upload
            const initRes = await apiClient.post('/uploads/init', {
                filename: file.name,
                total_chunks: 1
            });
            const uploadId = initRes.data.upload_id;

            // Step 2: Upload Chunk
            const formData = new FormData();
            formData.append('chunk_index', 0);
            formData.append('file', file);

            await apiClient.post(`/uploads/${uploadId}/chunk`, formData, {
                headers: { 'Content-Type': 'multipart/form-data' }
            });

            // Step 3: Complete Upload
            await apiClient.post(`/uploads/${uploadId}/complete`, {
                filename: file.name
            });

            // Step 4: Trigger Ingestion
            setMessage('Triggering ingestion job...');
            setStatus('processing');
            const ingestRes = await apiClient.post(endpoint, {
                upload_id: uploadId
            });

            // Capture Job ID from new response structure
            const newJobId = ingestRes.data.job_id;
            setJobId(newJobId);
            setMessage(`Ingestion Job #${newJobId} started!`);

        } catch (err) {
            console.error(err);
            setStatus('error');
            setMessage('Operation failed. Check console.');
        } finally {
            setUploading(false);
        }
    };

    // Poll for Job Status Updates (refined with step-based progress)
    useEffect(() => {
        if (!jobId) return;

        const checkJob = async () => {
            try {
                const res = await apiClient.get(`/jobs/${jobId}`);
                const job = res.data;

                // Find active or last step info
                if (job.steps && job.steps.length > 0) {
                    // prioritize running steps, else take the last one
                    const activeStep = job.steps.find(s => s.status === 'running') || job.steps[job.steps.length - 1];

                    if (activeStep) {
                        const pct = activeStep.progress_percentage || 0;
                        setProgress(pct);

                        if (job.status === 'completed') {
                            setStatus('success');
                            setMessage("Job Completed Successfully!");
                            setProgress(100);
                        } else if (job.status === 'failed') {
                            setStatus('error');
                            setMessage(job.error_message || "Job Failed");
                        } else {
                            setStatus('processing');
                            // Format: "Processing Users: 45%"
                            setMessage(`${activeStep.step_name}: ${Math.round(pct)}%`);
                        }
                    }
                }
            } catch (err) {
                console.error("Error polling job", err);
            }
        };

        const interval = setInterval(checkJob, 1000); // Poll faster for smooth progress
        return () => clearInterval(interval);
    }, [jobId]);

    return (
        <div className="space-y-6">
            <div className="rounded-xl p-6" style={{ background: 'var(--bg-hover)', border: '1px solid var(--border)' }}>
                <h2 className="text-xl font-semibold mb-2" style={{ color: 'var(--text-primary)' }}>{title}</h2>
                <p className="text-sm mb-6" style={{ color: 'var(--text-secondary)' }}>{description}</p>

                <div className="border-2 border-dashed rounded-lg p-8 text-center transition-colors" style={{ borderColor: 'var(--border)', background: 'var(--bg-card)' }}
                    onMouseEnter={(e) => e.currentTarget.style.borderColor = 'var(--accent)'}
                    onMouseLeave={(e) => e.currentTarget.style.borderColor = 'var(--border)'}
                >
                    <input
                        type="file"
                        id={`file-${title}`}
                        className="hidden"
                        accept={fileAccept}
                        onChange={handleFileChange}
                        disabled={uploading || status === 'processing'}
                    />
                    <label htmlFor={`file-${title}`} className="cursor-pointer flex flex-col items-center">
                        <FaUpload className="w-8 h-8 mb-3" style={{ color: 'var(--text-secondary)' }} />
                        <span className="font-medium" style={{ color: 'var(--text-primary)' }}>{file ? file.name : `Select ${fileLabel}`}</span>
                        <span className="text-xs mt-1" style={{ color: 'var(--text-tertiary)' }}>or drag and drop here</span>
                    </label>
                </div>

                {file && (
                    <button
                        onClick={handleUpload}
                        disabled={uploading || status === 'processing'}
                        className="mt-4 w-full py-3 rounded-lg font-medium flex items-center justify-center transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                        style={uploading || status === 'processing'
                            ? { background: 'var(--bg-hover)', color: 'var(--text-secondary)', cursor: 'not-allowed' }
                            : { background: 'var(--accent)', color: 'var(--text-on-accent)' }
                        }
                    >
                        {uploading || status === 'processing' ? (
                            <>
                                <FaSpinner className="animate-spin mr-2" /> Processing...
                            </>
                        ) : (
                            'Start Ingestion'
                        )}
                    </button>
                )}

                {status !== 'idle' && (
                    <div className="mt-4 p-4 rounded-lg flex flex-col" style={{
                        background: status === 'error' ? 'var(--danger-bg)' : status === 'success' ? 'var(--success-bg)' : 'var(--bg-accent-muted)',
                        color: status === 'error' ? 'var(--danger)' : status === 'success' ? 'var(--success)' : 'var(--accent)'
                    }}>
                        <div className="flex items-center mb-2">
                            {status === 'error' && <FaExclamationCircle className="mr-2" />}
                            {status === 'success' && <FaCheckCircle className="mr-2" />}
                            {status === 'processing' && <FaSpinner className="animate-spin mr-2" />}
                            <span className="font-semibold">{message}</span>
                        </div>

                        {/* Progress Bar */}
                        {(status === 'processing' || status === 'success') && (
                            <div className="w-full rounded-full h-2.5 mt-1" style={{ background: 'var(--bg-hover)' }}>
                                <div
                                    className="h-2.5 rounded-full transition-all duration-500 ease-out"
                                    style={{ width: `${progress}%`, backgroundColor: 'currentColor' }}
                                ></div>
                            </div>
                        )}
                    </div>
                )}
            </div>

            {/* Logs Section */}
            <div>
                <h3 className="text-lg font-medium mb-3 flex items-center" style={{ color: 'var(--text-primary)' }}>
                    <span className="w-2 h-2 rounded-full mr-2 animate-pulse" style={{ background: 'var(--accent)' }}></span>
                    Live Job Logs
                </h3>
                <LogViewer jobId={jobId} logType="celery" isActive={status === 'processing'} />
            </div>

            {/* Steps Breakdown */}
            {jobId && status !== 'idle' && (
                <JobSteps jobId={jobId} />
            )}
        </div>
    );
}

function JobSteps({ jobId }) {
    const [steps, setSteps] = useState([]);
    const [job, setJob] = useState(null);

    useEffect(() => {
        if (!jobId) return;
        const fetchJob = async () => {
            try {
                const res = await apiClient.get(`/jobs/${jobId}`);
                setSteps(res.data.steps || []);
                setJob(res.data);
            } catch (e) {
                console.error(e);
            }
        };
        fetchJob();
        const interval = setInterval(fetchJob, 2000);
        return () => clearInterval(interval);
    }, [jobId]);

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

    if (!steps.length) return null;

    return (
        <div className="rounded-xl p-6 mt-6" style={{ background: 'var(--bg-hover)', border: '1px solid var(--border)' }}>
            <h3 className="text-lg font-medium mb-4" style={{ color: 'var(--text-primary)' }}>Pipeline Steps</h3>

            {job && (
                <div className="mb-4 text-sm" style={{ color: 'var(--text-secondary)' }}>
                    Total Time: <span className="font-mono" style={{ color: 'var(--accent)' }}>
                        {formatDuration(job.started_at || job.created_at, job.completed_at)}
                    </span>
                </div>
            )}

            <div className="space-y-3">
                {steps.map((step) => (
                    <div key={step.id} className="flex items-center justify-between p-3 rounded-lg" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
                        <div className="flex items-center gap-3">
                            {step.status === 'completed' ? (
                                <FaCheckCircle style={{ color: 'var(--success)' }} />
                            ) : step.status === 'running' ? (
                                <FaSpinner className="animate-spin" style={{ color: 'var(--accent)' }} />
                            ) : step.status === 'failed' ? (
                                <FaExclamationCircle style={{ color: 'var(--danger)' }} />
                            ) : (
                                <div className="w-4 h-4 rounded-full" style={{ border: '2px solid var(--text-tertiary)' }} />
                            )}
                            <div>
                                <div className="font-medium" style={{ color: 'var(--text-primary)' }}>{step.step_name}</div>
                                {step.current_action && (
                                    <div className="text-xs" style={{ color: 'var(--text-tertiary)' }}>{step.current_action}</div>
                                )}
                            </div>
                        </div>
                        <div className="text-right">
                            <div className="text-xs uppercase tracking-wider font-semibold"
                                style={{ color: step.status === 'completed' ? 'var(--success)' : step.status === 'running' ? 'var(--accent)' : 'var(--text-tertiary)' }}>
                                {step.status}
                            </div>
                            <div className="text-xs font-mono mt-1" style={{ color: 'var(--text-secondary)' }}>
                                Time: {formatDuration(step.started_at, step.completed_at)}
                            </div>
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
}
