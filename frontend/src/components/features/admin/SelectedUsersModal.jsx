import React, { useState, useMemo } from "react";
import { PiTrashBold, PiUserBold, PiXBold, PiMagnifyingGlassBold, PiTrashSimpleBold } from "react-icons/pi";

export default function SelectedUsersModal({ isOpen, onClose, selectedUsers, onRemoveUser, onClearAll }) {
    const [searchQuery, setSearchQuery] = useState("");
    const [removeHoverId, setRemoveHoverId] = useState(null);

    const filteredUsers = useMemo(() => {
        if (!searchQuery.trim()) return selectedUsers;
        const q = searchQuery.toLowerCase();
        return selectedUsers.filter(user =>
            (user.name && user.name.toLowerCase().includes(q)) ||
            (user.profileName && user.profileName.toLowerCase().includes(q)) ||
            (user.serviceId && user.serviceId.toLowerCase().includes(q))
        );
    }, [selectedUsers, searchQuery]);

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 z-[200] flex items-center justify-center p-4">
            <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />
            <div className="relative w-full max-w-lg rounded-xl shadow-2xl flex flex-col max-h-[80vh]" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
                <div className="flex items-center justify-between p-4" style={{ borderBottom: '1px solid var(--border)' }}>
                    <h3 className="text-lg font-semibold" style={{ color: 'var(--text-primary)' }}>
                        Selected Users ({selectedUsers.length})
                    </h3>
                    <div className="flex items-center gap-2">
                        {selectedUsers.length > 0 && (
                            <button
                                onClick={() => {
                                    if (window.confirm("Are you sure you want to clear all selected users?")) {
                                        onClearAll();
                                    }
                                }}
                                className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md transition-colors"
                                style={{ color: 'var(--danger)' }}
                                onMouseEnter={(e) => e.currentTarget.style.background = 'var(--danger-bg)'}
                                onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
                                title="Clear all selections"
                            >
                                <PiTrashSimpleBold />
                                Clear All
                            </button>
                        )}
                        <button
                            onClick={onClose}
                            className="transition-colors p-1"
                            style={{ color: 'var(--text-secondary)' }}
                            onMouseEnter={(e) => e.currentTarget.style.color = 'var(--text-primary)'}
                            onMouseLeave={(e) => e.currentTarget.style.color = 'var(--text-secondary)'}
                        >
                            <PiXBold />
                        </button>
                    </div>
                </div>

                {/* Search Bar */}
                {selectedUsers.length > 0 && (
                    <div className="p-4" style={{ borderBottom: '1px solid var(--border)' }}>
                        <div className="relative">
                            <input
                                type="text"
                                value={searchQuery}
                                onChange={(e) => setSearchQuery(e.target.value)}
                                placeholder="Search in selection..."
                                className="si-input w-full pl-3 pr-9"
                            />
                            <PiMagnifyingGlassBold className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none" style={{ color: 'var(--text-tertiary)' }}
                            />
                        </div>
                    </div>
                )}

                <div className="flex-1 overflow-y-auto p-4 space-y-2 custom-scrollbar">
                    {selectedUsers.length === 0 ? (
                        <p className="text-sm text-center py-4" style={{ color: 'var(--text-tertiary)' }}>No users selected.</p>
                    ) : filteredUsers.length === 0 ? (
                        <p className="text-sm text-center py-4" style={{ color: 'var(--text-tertiary)' }}>No users match your search.</p>
                    ) : (
                        filteredUsers.map((user) => (
                            <div
                                key={user.serviceId}
                                className="flex items-center justify-between p-3 rounded-lg"
                                style={{ background: 'var(--bg-hover)', border: '1px solid color-mix(in srgb, var(--border) 50%, transparent)' }}
                            >
                                <div className="flex items-center gap-3 overflow-hidden">
                                    <div className="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
                                        <PiUserBold className="text-xs" style={{ color: 'var(--text-tertiary)' }} />
                                    </div>
                                    <div className="min-w-0">
                                        <p className="text-sm font-medium truncate" style={{ color: 'var(--text-primary)' }}>
                                            {user.name || user.profileName || "Unknown"}
                                        </p>
                                        <p className="text-xs font-mono truncate" style={{ color: 'var(--text-tertiary)' }}>
                                            {user.serviceId}
                                        </p>
                                    </div>
                                </div>
                                <button
                                    onClick={() => onRemoveUser(user.serviceId)}
                                    className="p-2 rounded transition-colors ml-2"
                                    style={{
                                        color: removeHoverId === user.serviceId ? 'var(--danger)' : 'var(--text-secondary)',
                                        background: removeHoverId === user.serviceId ? 'var(--bg-hover)' : 'transparent',
                                    }}
                                    onMouseEnter={() => setRemoveHoverId(user.serviceId)}
                                    onMouseLeave={() => setRemoveHoverId(null)}
                                    title="Remove from selection"
                                >
                                    <PiTrashBold />
                                </button>
                            </div>
                        ))
                    )}
                </div>

                <div className="p-4 flex justify-end" style={{ borderTop: '1px solid var(--border)' }}>
                    <button
                        onClick={onClose}
                        className="si-button-secondary"
                    >
                        Done
                    </button>
                </div>
            </div>
        </div>
    );
}
