import React, { useState } from "react";
import { useDispatch } from "react-redux";
import toast from "react-hot-toast";
import { clearCreatedKey } from "../../../store/slices/apiKeySlice";
import {
    PiXBold,
    PiCopyBold,
    PiCheckBold,
    PiWarningBold,
    PiDownloadBold,
} from "react-icons/pi";

export default function ApiKeyDetail({ keyData, onClose }) {
    const dispatch = useDispatch();
    const [copied, setCopied] = useState(false);

    const handleCopy = () => {
        navigator.clipboard.writeText(keyData.raw_key);
        setCopied(true);
        toast.success("API key copied to clipboard");
        setTimeout(() => setCopied(false), 2000);
    };

    const handleDownload = () => {
        const content = JSON.stringify({
            key_id: keyData.key_id,
            api_key: keyData.raw_key,
            name: keyData.name,
            created_at: keyData.created_at,
            expires_at: keyData.expires_at,
        }, null, 2);
        const blob = new Blob([content], { type: "application/json" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `${keyData.name.replace(/\s+/g, '_')}_api_key.json`;
        a.click();
        URL.revokeObjectURL(url);
    };

    const handleClose = () => {
        dispatch(clearCreatedKey());
        onClose();
    };

    const exampleCurl = `curl -H "X-API-Key: ${keyData.raw_key}" \\
  "${window.location.origin}/api/v1/public/users/search?q=example"`;

    return (
        <div className="fixed inset-0 z-[200] flex items-center justify-center p-4">
            <div className="absolute inset-0 bg-black/60" />
            <div className="relative rounded-xl w-full max-w-lg shadow-2xl" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
                {/* Header */}
                <div className="flex items-center justify-between px-6 py-4" style={{ borderBottom: '1px solid var(--border)' }}>
                    <h3 className="text-lg font-bold" style={{ color: 'var(--text-primary)' }}>Your New API Key</h3>
                    <button onClick={handleClose} className="si-icon-button">
                        <PiXBold />
                    </button>
                </div>

                <div className="p-6 space-y-5">
                    {/* Warning */}
                    <div className="flex items-start gap-3 rounded-lg p-3" style={{ background: 'var(--warning-bg)', border: '1px solid var(--warning)' }}>
                        <PiWarningBold className="text-lg mt-0.5 flex-shrink-0" style={{ color: 'var(--warning)' }} />
                        <p className="text-sm" style={{ color: 'var(--warning)' }}>
                            Copy this key now. It will <strong>not</strong> be shown again after you close this dialog.
                        </p>
                    </div>

                    {/* Key Display */}
                    <div>
                        <label className="block text-xs mb-1.5" style={{ color: 'var(--text-tertiary)' }}>API Key</label>
                        <div className="flex items-center gap-2">
                            <div className="flex-1 rounded-lg px-3 py-2.5 font-mono text-sm break-all select-all" style={{ background: 'var(--bg-hover)', border: '1px solid var(--border)', color: 'var(--accent)' }}>
                                {keyData.raw_key}
                            </div>
                            <button
                                onClick={handleCopy}
                                className="si-icon-button flex-shrink-0"
                                style={copied ? { background: 'var(--success-bg)', borderColor: 'var(--success)', color: 'var(--success)' } : {}}
                                title="Copy to clipboard"
                            >
                                {copied ? <PiCheckBold /> : <PiCopyBold />}
                            </button>
                        </div>
                    </div>

                    {/* Key Info */}
                    <div className="grid grid-cols-2 gap-4 text-sm">
                        <div>
                            <span className="text-xs" style={{ color: 'var(--text-tertiary)' }}>Name</span>
                            <p style={{ color: 'var(--text-primary)' }}>{keyData.name}</p>
                        </div>
                        <div>
                            <span className="text-xs" style={{ color: 'var(--text-tertiary)' }}>Key ID</span>
                            <p className="font-mono text-xs" style={{ color: 'var(--text-primary)' }}>{keyData.key_id}</p>
                        </div>
                        <div>
                            <span className="text-xs" style={{ color: 'var(--text-tertiary)' }}>Expires</span>
                            <p style={{ color: 'var(--text-primary)' }}>{keyData.expires_at ? new Date(keyData.expires_at).toLocaleDateString() : "Never"}</p>
                        </div>
                        <div>
                            <span className="text-xs" style={{ color: 'var(--text-tertiary)' }}>Quota</span>
                            <p style={{ color: 'var(--text-primary)' }}>{keyData.quota_limit || "Default"} req/min</p>
                        </div>
                    </div>

                    {/* Usage Example */}
                    <div>
                        <label className="block text-xs mb-1.5" style={{ color: 'var(--text-tertiary)' }}>Usage Example</label>
                        <pre className="rounded-lg px-3 py-2.5 text-xs overflow-x-auto custom-scrollbar" style={{ background: 'var(--bg-hover)', border: '1px solid var(--border)', color: 'var(--text-primary)' }}>
                            {exampleCurl}
                        </pre>
                    </div>

                    {/* Actions */}
                    <div className="flex items-center gap-3 justify-end pt-1">
                        <button
                            onClick={handleDownload}
                            className="si-button-secondary"
                        >
                            <PiDownloadBold /> Download
                        </button>
                        <button
                            onClick={handleClose}
                            className="si-button-primary"
                        >
                            Done
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
}
