import React, { useState, useRef, useEffect, useCallback } from "react";
import toast from "react-hot-toast";
import apiClient from "../../../services/api";
import { adminApi } from "../../../services/adminApi";
import DeleteConfirmModal from "./DeleteConfirmModal";
import SelectedUsersModal from "./SelectedUsersModal";
import {
    PiTrashBold,
    PiCheckCircleBold,
    PiWarningCircleBold,
    PiUploadBold,
    PiUserBold,
    PiPhoneBold,
    PiUsersThreeBold,
    PiCaretDownBold,
    PiCaretUpBold
} from "react-icons/pi";

const REASON_OPTIONS = [
    { value: "Illegal Content", label: "Illegal Content" },
    { value: "Spam/Abuse", label: "Spam/Abuse" },
    { value: "Legal Request", label: "Legal Request" },
    { value: "False Persona", label: "False Persona" },
    { value: "Policy Violation", label: "Policy Violation" },
    { value: "Other", label: "Other" },
];

export default function DeleteUserForm() {
    // Selection state
    const [selectedUsers, setSelectedUsers] = useState([]);

    // Form fields
    const [reason, setReason] = useState("");
    const [notes, setNotes] = useState("");

    // Search state
    const [searchQuery, setSearchQuery] = useState("");
    const [searchResults, setSearchResults] = useState([]);
    const [searchLoading, setSearchLoading] = useState(false);
    const [showDropdown, setShowDropdown] = useState(false);
    const [selectedIndex, setSelectedIndex] = useState(-1);

    // Import state
    const [showImport, setShowImport] = useState(false);
    const [bulkIdsInput, setBulkIdsInput] = useState("");

    // Modals & UI States
    const [showSelectedModal, setShowSelectedModal] = useState(false);
    const [showConfirm, setShowConfirm] = useState(false);
    const [isDeleting, setIsDeleting] = useState(false);

    // Results
    const [result, setResult] = useState(null);
    const [error, setError] = useState("");

    // Hover state for delete button
    const [deleteHover, setDeleteHover] = useState(false);

    const dropdownRef = useRef(null);
    const inputRef = useRef(null);
    const debounceRef = useRef(null);

    // --- Live Search ---
    const doSearch = useCallback(async (query) => {
        if (!query || query.trim().length < 2) {
            setSearchResults([]);
            setShowDropdown(false);
            return;
        }
        setSearchLoading(true);
        try {
            const res = await apiClient.post("/users/search", {
                q: query.trim(),
                limit: 8,
                offset: 0,
            });
            const users = res.data?.data || [];
            setSearchResults(users);
            setShowDropdown(users.length > 0);
            setSelectedIndex(-1);
        } catch {
            setSearchResults([]);
            setShowDropdown(false);
        } finally {
            setSearchLoading(false);
        }
    }, []);

    const handleSearchInput = (value) => {
        setSearchQuery(value);
        if (debounceRef.current) clearTimeout(debounceRef.current);
        debounceRef.current = setTimeout(() => doSearch(value), 300);
    };

    useEffect(() => {
        return () => {
            if (debounceRef.current) clearTimeout(debounceRef.current);
        };
    }, []);

    useEffect(() => {
        const handleClickOutside = (e) => {
            if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
                setShowDropdown(false);
            }
        };
        document.addEventListener("mousedown", handleClickOutside);
        return () => document.removeEventListener("mousedown", handleClickOutside);
    }, []);

    // --- Multi-Select Logic ---
    const selectUser = (user) => {
        setSelectedUsers(prev => {
            if (prev.some(u => u.serviceId === user.serviceId)) return prev;
            return [...prev, user];
        });
        setSearchQuery("");
        setShowDropdown(false);
        setSearchResults([]);
        if (inputRef.current) inputRef.current.focus();
    };

    const removeSelectedUser = (serviceId) => {
        setSelectedUsers(prev => prev.filter(u => u.serviceId !== serviceId));
        if (selectedUsers.length <= 1) {
            setShowSelectedModal(false);
        }
    };

    const handleKeyDown = (e) => {
        if (!showDropdown || searchResults.length === 0) return;
        if (e.key === "ArrowDown") {
            e.preventDefault();
            setSelectedIndex((prev) => Math.min(prev + 1, searchResults.length - 1));
        } else if (e.key === "ArrowUp") {
            e.preventDefault();
            setSelectedIndex((prev) => Math.max(prev - 1, 0));
        } else if (e.key === "Enter") {
            e.preventDefault();
            if (selectedIndex >= 0 && selectedIndex < searchResults.length) {
                selectUser(searchResults[selectedIndex]);
            }
        } else if (e.key === "Escape") {
            setShowDropdown(false);
        }
    };

    // --- Import state ---
    const [importLoading, setImportLoading] = useState(false);

    // --- Import Parsing ---
    const parseBulkInput = async (text) => {
        const ids = text
            .split(/[,\n]+/)
            .map((id) => id.trim())
            .filter((id) => id.length > 0);

        if (ids.length === 0) {
            toast.error("No valid IDs found in input");
            return;
        }

        // Filter out IDs already selected
        const existingIds = new Set(selectedUsers.map(u => u.serviceId));
        const newIds = ids.filter(id => !existingIds.has(id));

        if (newIds.length === 0) {
            toast("All IDs already in the list", { icon: '\u2139\uFE0F' });
            return;
        }

        setImportLoading(true);
        try {
            // Validate each ID against the backend
            const results = await Promise.allSettled(
                newIds.map(id =>
                    apiClient.post("/users/search", { service_id: id, limit: 1, offset: 0 })
                )
            );

            const validUsers = [];
            const invalidIds = [];

            results.forEach((result, idx) => {
                if (result.status === "fulfilled" && result.value.data?.data?.length > 0) {
                    validUsers.push(result.value.data.data[0]);
                } else {
                    invalidIds.push(newIds[idx]);
                }
            });

            if (validUsers.length > 0) {
                setSelectedUsers(prev => {
                    const currentIds = new Set(prev.map(u => u.serviceId));
                    const uniqueNew = validUsers.filter(u => !currentIds.has(u.serviceId));
                    return [...prev, ...uniqueNew];
                });
                toast.success(`${validUsers.length} user${validUsers.length !== 1 ? 's' : ''} added`);
            }

            if (invalidIds.length > 0) {
                toast.error(`${invalidIds.length} ID${invalidIds.length !== 1 ? 's' : ''} not found: ${invalidIds.slice(0, 5).join(", ")}${invalidIds.length > 5 ? "..." : ""}`);
            }
        } catch {
            toast.error("Failed to validate IDs");
        } finally {
            setImportLoading(false);
        }

        setBulkIdsInput("");
        setShowImport(false);
    };

    const handleCsvUpload = (e) => {
        const file = e.target.files?.[0];
        if (!file) return;
        const reader = new FileReader();
        reader.onload = (ev) => {
            const text = ev.target.result;
            const lines = text.split("\n").filter((l) => l.trim());
            const ids = lines.map((l) => l.split(",")[0].trim()).filter((id) => id && id !== "service_id" && id.length > 0);

            if (ids.length === 0) {
                toast.error("No valid IDs found in CSV");
                return;
            }

            const newUsers = ids.map(id => ({ serviceId: id, name: "Imported ID", e164: null }));
            setSelectedUsers(prev => {
                const existingIds = new Set(prev.map(u => u.serviceId));
                const uniqueNew = newUsers.filter(u => !existingIds.has(u.serviceId));
                if (uniqueNew.length === 0) {
                    toast("All IDs already in the list", { icon: '\u2139\uFE0F' });
                } else {
                    toast.success(`${uniqueNew.length} ID${uniqueNew.length !== 1 ? 's' : ''} imported from CSV`);
                }
                return [...prev, ...uniqueNew];
            });
        };
        reader.readAsText(file);
        e.target.value = null;
    };

    // --- Deletion Flow ---
    const handleBulkDelete = async () => {
        if (selectedUsers.length === 0) return;
        setIsDeleting(true);
        setError("");
        setResult(null);
        try {
            const serviceIds = selectedUsers.map(u => u.serviceId);
            const res = await adminApi.bulkDeleteUsers({
                service_ids: serviceIds,
                reason,
                notes: notes || null,
            });
            setResult(res.data);
            setShowConfirm(false);
            const deletedCount = selectedUsers.length;
            setSelectedUsers([]);
            setNotes("");

            if (res.data.errors?.length > 0) {
                toast(`${res.data.succeeded} deleted, ${res.data.failed} failed`, { icon: '\u26A0\uFE0F' });
            } else {
                toast.success(`${deletedCount} user${deletedCount !== 1 ? 's' : ''} deleted successfully`);
            }
        } catch (err) {
            const msg = err.response?.data?.detail || "Deletion failed.";
            setError(msg);
            setShowConfirm(false);
            toast.error(msg);
        } finally {
            setIsDeleting(false);
        }
    };

    const canDelete = selectedUsers.length > 0 && reason.trim().length > 0;
    const isSingle = selectedUsers.length === 1;

    // --- UI Helpers ---
    const getUserDisplayName = (user) => {
        return user.name || user.profileName || user.profileFullName || null;
    };

    return (
        <div className="max-w-3xl">
            {/* Find Users Bar */}
            <div className="space-y-4">
                <div ref={dropdownRef} className="relative">
                    <label className="flex items-center justify-between text-sm font-medium mb-1" style={{ color: 'var(--text-primary)' }}>
                        <span>Find Users to Delete</span>
                        <button
                            onClick={() => setShowImport(!showImport)}
                            className="text-xs flex items-center gap-1 transition-colors"
                            style={{ color: 'var(--accent)' }}
                        >
                            {showImport ? <PiCaretUpBold /> : <PiCaretDownBold />}
                            Import Multiple IDs
                        </button>
                    </label>
                    <div className="relative">
                        <input
                            ref={inputRef}
                            type="text"
                            value={searchQuery}
                            onChange={(e) => handleSearchInput(e.target.value)}
                            onKeyDown={handleKeyDown}
                            onFocus={() => {
                                if (searchResults.length > 0) setShowDropdown(true);
                            }}
                            placeholder="Search by name, phone number, service ID..."
                            className="si-input w-full pl-3 pr-9 py-3"
                        />
                        {searchLoading ? (
                            <div className="absolute right-3 top-1/2 -translate-y-1/2">
                                <div className="w-4 h-4 border-2 rounded-full animate-spin" style={{ borderColor: 'color-mix(in srgb, var(--accent) 30%, transparent)', borderTopColor: 'var(--accent)' }} />
                            </div>
                        ) : (
                            <svg className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 pointer-events-none" style={{ color: 'var(--text-tertiary)' }} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                            </svg>
                        )}
                    </div>

                    {/* Dropdown */}
                    {showDropdown && searchResults.length > 0 && (
                        <div className="absolute z-50 w-full mt-1 rounded-lg shadow-2xl max-h-[320px] overflow-y-auto custom-scrollbar" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
                            {searchResults.map((user, idx) => {
                                const displayName = getUserDisplayName(user);
                                return (
                                    <button
                                        key={user.serviceId}
                                        onClick={() => selectUser(user)}
                                        className="w-full text-left px-3 py-2.5 flex items-start gap-3 transition-colors last:border-b-0"
                                        style={{
                                            background: idx === selectedIndex ? 'color-mix(in srgb, var(--accent) 10%, transparent)' : 'transparent',
                                            borderBottom: '1px solid color-mix(in srgb, var(--border) 50%, transparent)',
                                        }}
                                        onMouseEnter={(e) => { if (idx !== selectedIndex) e.currentTarget.style.background = 'var(--bg-hover)'; }}
                                        onMouseLeave={(e) => { if (idx !== selectedIndex) e.currentTarget.style.background = 'transparent'; }}
                                    >
                                        <div className="w-9 h-9 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5" style={{ background: 'var(--bg-hover)', border: '1px solid var(--border)' }}>
                                            <PiUserBold className="text-sm" style={{ color: 'var(--text-tertiary)' }} />
                                        </div>
                                        <div className="flex-1 min-w-0">
                                            <div className="flex items-center gap-2">
                                                <span className="text-sm font-medium truncate" style={{ color: 'var(--text-primary)' }}>
                                                    {displayName || "Unknown"}
                                                </span>
                                            </div>
                                            <div className="flex items-center gap-3 mt-0.5">
                                                <span className="text-xs font-mono truncate" style={{ color: 'var(--text-tertiary)' }} title={user.serviceId}>
                                                    {user.serviceId}
                                                </span>
                                                {user.e164 && (
                                                    <span className="flex items-center gap-1 text-xs" style={{ color: 'var(--text-secondary)' }}>
                                                        <PiPhoneBold className="text-[10px]" />
                                                        {user.e164}
                                                    </span>
                                                )}
                                                {user.groupCount > 0 && (
                                                    <span className="flex items-center gap-1 text-xs" style={{ color: 'var(--text-secondary)' }}>
                                                        <PiUsersThreeBold className="text-[10px]" />
                                                        {user.groupCount}
                                                    </span>
                                                )}
                                            </div>
                                        </div>
                                    </button>
                                );
                            })}
                        </div>
                    )}
                </div>

                {/* Import Box */}
                {showImport && (
                    <div className="rounded-lg p-3 space-y-3" style={{ background: 'var(--bg-hover)', border: '1px solid var(--border)' }}>
                        <textarea
                            value={bulkIdsInput}
                            onChange={(e) => setBulkIdsInput(e.target.value)}
                            rows={5}
                            placeholder="Paste service IDs here, separated by commas or newlines..."
                            className="si-input w-full block font-mono text-sm"
                            style={{ minHeight: 120, resize: 'vertical' }}
                        />
                        <div className="flex flex-wrap items-center gap-2">
                            <button
                                onClick={() => parseBulkInput(bulkIdsInput)}
                                disabled={!bulkIdsInput.trim() || importLoading}
                                className="si-button-primary text-sm disabled:opacity-30 flex-1 sm:flex-none justify-center"
                            >
                                {importLoading ? "Validating..." : "Add IDs"}
                            </button>
                            <span className="text-xs" style={{ color: 'var(--text-tertiary)' }}>or</span>
                            <label className="si-button-secondary flex items-center justify-center gap-1.5 text-sm cursor-pointer flex-1 sm:flex-none">
                                <PiUploadBold />
                                Upload CSV
                                <input
                                    type="file"
                                    accept=".csv"
                                    onChange={handleCsvUpload}
                                    className="hidden"
                                />
                            </label>
                        </div>
                    </div>
                )}

                {/* Selected Indicators */}
                {selectedUsers.length > 0 && (
                    <div className="flex items-center gap-3 p-2 rounded-lg" style={{ background: 'var(--bg-hover)', border: '1px solid var(--border)' }}>
                        <div className="flex items-center gap-2 flex-1">
                            <div className="flex -space-x-2 overflow-hidden px-1">
                                {selectedUsers.slice(0, 3).map((u, i) => (
                                    <div key={i} className="inline-block h-6 w-6 rounded-full flex items-center justify-center relative z-10" style={{ background: 'var(--bg-hover)', border: '2px solid var(--bg-card)' }}>
                                        <PiUserBold className="text-[10px]" style={{ color: 'var(--text-secondary)' }} />
                                    </div>
                                ))}
                                {selectedUsers.length > 3 && (
                                    <div className="inline-block h-6 w-6 rounded-full flex items-center justify-center relative z-0" style={{ background: 'var(--bg-hover)', border: '2px solid var(--bg-card)' }}>
                                        <span className="text-[10px]" style={{ color: 'var(--text-primary)' }}>+{selectedUsers.length - 3}</span>
                                    </div>
                                )}
                            </div>
                            <span className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
                                {selectedUsers.length} user{selectedUsers.length === 1 ? '' : 's'} staged for deletion.
                            </span>
                        </div>
                        <button
                            onClick={() => setShowSelectedModal(true)}
                            className="si-button-secondary text-xs"
                        >
                            View / Edit List
                        </button>
                    </div>
                )}
            </div>

            {/* Reason & Notes Fields */}
            <div className="space-y-4 mt-6">
                <div>
                    <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-primary)' }}>
                        Reason for Deletion <span style={{ color: 'var(--danger)' }}>*</span>
                    </label>
                    <select
                        value={reason}
                        onChange={(e) => setReason(e.target.value)}
                        className="si-select w-full"
                    >
                        <option value="">Select a reason...</option>
                        {REASON_OPTIONS.map((opt) => (
                            <option key={opt.value} value={opt.value}>
                                {opt.label}
                            </option>
                        ))}
                    </select>
                </div>

                <div>
                    <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-primary)' }}>
                        Additional Notes <span style={{ color: 'var(--text-tertiary)' }}>(optional)</span>
                    </label>
                    <textarea
                        value={notes}
                        onChange={(e) => setNotes(e.target.value.slice(0, 500))}
                        rows={5}
                        maxLength={500}
                        placeholder="Optional notes about this deletion..."
                        className="si-input w-full"
                        style={{ padding: '12px', minHeight: '120px' }}
                    />
                    <p className="text-xs mt-1" style={{ color: 'var(--text-tertiary)' }}>{notes.length}/500</p>
                </div>

                {/* Submit Action */}
                <button
                    onClick={() => setShowConfirm(true)}
                    disabled={!canDelete}
                    className="flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-medium transition-colors"
                    style={{
                        background: canDelete ? (deleteHover ? 'color-mix(in srgb, var(--danger) 85%, black)' : 'var(--danger)') : 'var(--danger-bg)',
                        color: canDelete ? '#ffffff' : 'color-mix(in srgb, var(--danger) 50%, transparent)',
                        cursor: canDelete ? 'pointer' : 'not-allowed',
                    }}
                    onMouseEnter={() => setDeleteHover(true)}
                    onMouseLeave={() => setDeleteHover(false)}
                >
                    <PiTrashBold />
                    Delete {selectedUsers.length > 0 ? selectedUsers.length : ""} User{selectedUsers.length !== 1 ? 's' : ''}
                </button>
            </div>

            {/* Success/Error Results */}
            {result && (
                <div className="mt-6 rounded-lg p-4" style={{ background: 'var(--success-bg)', border: '1px solid color-mix(in srgb, var(--success) 20%, transparent)' }}>
                    <div className="flex items-center gap-2 mb-2">
                        <PiCheckCircleBold style={{ color: 'var(--success)' }} />
                        <span className="text-sm font-medium" style={{ color: 'var(--success)' }}>Deletion Completed</span>
                    </div>
                    {selectedUsers.length === 1 && result.audit_id && !result.errors?.length ? (
                        <div className="text-sm space-y-1" style={{ color: 'var(--text-primary)' }}>
                            <p>Service ID: <span className="font-mono" style={{ color: 'var(--text-primary)' }}>{result.service_id}</span></p>
                            <p>Audit ID: <span className="font-mono" style={{ color: 'var(--text-primary)' }}>{result.audit_id}</span></p>
                        </div>
                    ) : (
                        <div className="text-sm space-y-1" style={{ color: 'var(--text-primary)' }}>
                            <p>Total Processed: {result.total} | Succeeded: <span style={{ color: 'var(--success)' }}>{result.succeeded}</span> | Failed: <span style={{ color: 'var(--danger)' }}>{result.failed}</span></p>
                            {result.errors?.length > 0 && (
                                <div className="mt-2 max-h-40 overflow-y-auto custom-scrollbar p-2 rounded" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
                                    <p className="text-xs font-medium mb-1 pb-1" style={{ color: 'var(--danger)', borderBottom: '1px solid var(--border)' }}>Failures / Exclusions:</p>
                                    {result.errors.map((err, i) => (
                                        <p key={i} className="text-xs font-mono mb-1" style={{ color: 'var(--text-primary)' }}>
                                            {err.service_id}: <span className="font-sans" style={{ color: 'var(--danger)' }}>{err.error}</span>
                                        </p>
                                    ))}
                                </div>
                            )}
                        </div>
                    )}
                </div>
            )}

            {error && (
                <div className="mt-6 rounded-lg p-4 flex items-center gap-2" style={{ background: 'var(--danger-bg)', border: '1px solid color-mix(in srgb, var(--danger) 20%, transparent)' }}>
                    <PiWarningCircleBold style={{ color: 'var(--danger)' }} />
                    <span className="text-sm" style={{ color: 'var(--danger)' }}>{error}</span>
                </div>
            )}

            {/* Modals */}
            <SelectedUsersModal
                isOpen={showSelectedModal}
                onClose={() => setShowSelectedModal(false)}
                selectedUsers={selectedUsers}
                onRemoveUser={removeSelectedUser}
                onClearAll={() => setSelectedUsers([])}
            />

            <DeleteConfirmModal
                isOpen={showConfirm}
                onClose={() => setShowConfirm(false)}
                onConfirm={handleBulkDelete}
                previewData={isSingle ? selectedUsers[0] : null}
                reason={reason}
                notes={notes}
                isBulk={!isSingle}
                bulkCount={selectedUsers.length}
                isLoading={isDeleting}
            />
        </div>
    );
}
