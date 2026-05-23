import React, { useState, useEffect, useRef } from 'react';
import apiClient from '../../services/api';
import { PiCaretDownBold, PiXBold } from "react-icons/pi";

const GroupAutocomplete = ({ value, onChange, placeholder = "Search Group...", className = "" }) => {
    const [inputValue, setInputValue] = useState(value?.name || '');
    const [suggestions, setSuggestions] = useState([]);
    const [isLoading, setIsLoading] = useState(false);
    const [isOpen, setIsOpen] = useState(false);
    const wrapperRef = useRef(null);

    // Sync input with value prop (e.g. initial state)
    useEffect(() => {
        if (value && value.name !== inputValue) {
            setInputValue(value.name);
        } else if (!value) {
            setInputValue('');
        }
    }, [value]);

    useEffect(() => {
        const handleClickOutside = (event) => {
            if (wrapperRef.current && !wrapperRef.current.contains(event.target)) {
                setIsOpen(false);
            }
        };
        document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, []);

    const fetchGroups = async (query) => {
        if (!query) {
            setSuggestions([]);
            return;
        }
        setIsLoading(true);
        try {
            const response = await apiClient.post('/groups/search', {
                q: query,
                limit: 10
            });
            setSuggestions(response.data || []);
            setIsOpen(true);
        } catch (error) {
            console.error("Error fetching groups:", error);
        } finally {
            setIsLoading(false);
        }
    };

    // Debounce
    useEffect(() => {
        const timer = setTimeout(() => {
            if (inputValue && (!value || inputValue !== value.name)) {
                fetchGroups(inputValue);
            }
        }, 300);

        return () => clearTimeout(timer);
    }, [inputValue, value]);

    const handleSelect = (group) => {
        setInputValue(group.groupName);
        onChange({ id: group.groupId, name: group.groupName });
        setIsOpen(false);
    };

    const handleClear = (e) => {
        e.stopPropagation();
        setInputValue('');
        onChange(null);
        setSuggestions([]);
        setIsOpen(false);
    };

    return (
        <div className={`relative w-full ${className}`} ref={wrapperRef}>
            <div className="relative">
                <input
                    type="text"
                    className="si-input w-full rounded-lg pl-3 pr-8 py-2 text-sm transition-all"
                    placeholder={placeholder}
                    value={inputValue}
                    onChange={(e) => {
                        const val = e.target.value;
                        setInputValue(val);
                        // Notify parent about text change (partial search)
                        onChange(val ? { id: '', name: val } : null);
                    }}
                    onFocus={() => {
                        if (inputValue && suggestions.length > 0) setIsOpen(true);
                    }}
                />

                {value ? (
                    <button
                        onClick={handleClear}
                        className="absolute inset-y-0 right-0 pr-3 flex items-center"
                        style={{ color: 'var(--text-secondary)' }}
                        onMouseEnter={(e) => e.currentTarget.style.color = 'var(--text-primary)'}
                        onMouseLeave={(e) => e.currentTarget.style.color = 'var(--text-secondary)'}
                    >
                        <PiXBold />
                    </button>
                ) : (
                    <div className="absolute inset-y-0 right-0 pr-3 flex items-center pointer-events-none" style={{ color: 'var(--text-tertiary)' }}>
                        <PiCaretDownBold />
                    </div>
                )}
            </div>

            {isOpen && suggestions.length > 0 && (
                <ul className="absolute z-10 w-full mt-1 rounded-lg shadow-xl max-h-60 overflow-auto custom-scrollbar" style={{ background: 'var(--bg-hover)', border: '1px solid var(--border)' }}>
                    {suggestions.map((group) => (
                        <li
                            key={group.groupId}
                            onClick={() => handleSelect(group)}
                            className="px-4 py-2 cursor-pointer flex justify-between items-center group"
                            onMouseEnter={(e) => e.currentTarget.style.background = 'var(--bg-card)'}
                            onMouseLeave={(e) => e.currentTarget.style.background = ''}
                        >
                            <span className="text-sm font-medium truncate" style={{ color: 'var(--text-primary)' }}>
                                {group.groupName}
                            </span>
                            <span className="text-xs font-mono" style={{ color: 'var(--text-tertiary)' }}>
                                {group.numberOfMembers || 0}
                            </span>
                        </li>
                    ))}
                </ul>
            )}

            {isOpen && isLoading && (
                <div className="absolute z-10 w-full mt-1 rounded-lg shadow-xl p-2 text-center text-xs" style={{ background: 'var(--bg-hover)', border: '1px solid var(--border)', color: 'var(--text-tertiary)' }}>
                    Loading...
                </div>
            )}
        </div>
    );
};

export default GroupAutocomplete;
