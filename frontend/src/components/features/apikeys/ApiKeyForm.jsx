import React, { useState } from "react";
import { useDispatch } from "react-redux";
import toast from "react-hot-toast";
import { createApiKey } from "../../../store/slices/apiKeySlice";
import { PiXBold, PiKeyBold } from "react-icons/pi";

const EXPIRY_OPTIONS = [
    { value: "30", label: "30 days" },
    { value: "90", label: "90 days" },
    { value: "365", label: "1 year" },
];

export default function ApiKeyForm({ onClose }) {
    const dispatch = useDispatch();
    const [name, setName] = useState("");
    const [description, setDescription] = useState("");
    const [expiresInDays, setExpiresInDays] = useState("30");
    const [submitting, setSubmitting] = useState(false);

    const handleSubmit = async (e) => {
        e.preventDefault();
        if (!name.trim()) {
            toast.error("Key name is required");
            return;
        }
        setSubmitting(true);
        try {
            const data = {
                name: name.trim(),
                description: description.trim() || null,
                expires_in_days: parseInt(expiresInDays),
            };
            await dispatch(createApiKey(data)).unwrap();
            toast.success("API key created");
        } catch (err) {
            toast.error(err || "Failed to create key");
        } finally {
            setSubmitting(false);
        }
    };

    return (
        <div className="fixed inset-0 z-[200] flex items-center justify-center p-4">
            <div className="absolute inset-0 bg-black/60" onClick={onClose} />
            <div className="relative rounded-xl w-full max-w-md shadow-2xl" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
                {/* Header */}
                <div className="flex items-center justify-between px-6 py-4" style={{ borderBottom: '1px solid var(--border)' }}>
                    <div className="flex items-center gap-2">
                        <PiKeyBold style={{ color: 'var(--accent)' }} />
                        <h3 className="text-lg font-bold" style={{ color: 'var(--text-primary)' }}>Create API Key</h3>
                    </div>
                    <button onClick={onClose} className="si-icon-button">
                        <PiXBold />
                    </button>
                </div>

                {/* Form */}
                <form onSubmit={handleSubmit} className="p-6 space-y-4">
                    <div>
                        <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-primary)' }}>
                            Key Name <span style={{ color: 'var(--danger)' }}>*</span>
                        </label>
                        <input
                            type="text"
                            value={name}
                            onChange={(e) => setName(e.target.value.slice(0, 50))}
                            maxLength={50}
                            placeholder="e.g. Production API Key"
                            className="si-input"
                            autoFocus
                        />
                        <p className="text-xs mt-1" style={{ color: 'var(--text-tertiary)' }}>{name.length}/50</p>
                    </div>

                    <div>
                        <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-primary)' }}>
                            Description <span style={{ color: 'var(--text-tertiary)' }}>(optional)</span>
                        </label>
                        <textarea
                            value={description}
                            onChange={(e) => setDescription(e.target.value.slice(0, 200))}
                            maxLength={200}
                            rows={2}
                            placeholder="What will this key be used for?"
                            className="si-input"
                            style={{ height: 'auto', padding: '10px 12px' }}
                        />
                        <p className="text-xs mt-1" style={{ color: 'var(--text-tertiary)' }}>{description.length}/200</p>
                    </div>

                    <div>
                        <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-primary)' }}>Expiration</label>
                        <select
                            value={expiresInDays}
                            onChange={(e) => setExpiresInDays(e.target.value)}
                            className="si-select"
                        >
                            {EXPIRY_OPTIONS.map((opt) => (
                                <option key={opt.value} value={opt.value}>{opt.label}</option>
                            ))}
                        </select>
                    </div>

                    {/* Actions */}
                    <div className="flex items-center gap-3 justify-end pt-2">
                        <button
                            type="button"
                            onClick={onClose}
                            className="si-button-secondary"
                        >
                            Cancel
                        </button>
                        <button
                            type="submit"
                            disabled={submitting || !name.trim()}
                            className="si-button-primary"
                            style={{ opacity: submitting || !name.trim() ? 0.4 : 1 }}
                        >
                            {submitting && <div className="w-4 h-4 border-2 rounded-full animate-spin" style={{ borderColor: 'var(--text-on-accent)', borderTopColor: 'transparent' }} />}
                            Create Key
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
}
