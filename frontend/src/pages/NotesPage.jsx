import React, { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import { PiNotePencilBold, PiSpinnerGapBold, PiWarningCircleBold } from 'react-icons/pi';
import apiClient from '../services/api';

const NotesPage = () => {
    const [content, setContent] = useState('');
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        const fetchNotes = async () => {
            try {
                const response = await apiClient.get('/docs/notes');
                setContent(response.data.content);
            } catch (err) {
                console.error('Failed to fetch notes:', err);
                setError('Failed to load notes content.');
            } finally {
                setLoading(false);
            }
        };

        fetchNotes();
    }, []);

    if (loading) {
        return (
            <div className="flex flex-col items-center justify-center h-full" style={{ color: 'var(--text-secondary)' }}>
                <PiSpinnerGapBold className="text-4xl animate-spin mb-4" style={{ color: 'var(--accent)' }} />
                <p className="text-sm font-medium">Loading notes...</p>
            </div>
        );
    }

    if (error) {
        return (
            <div className="flex flex-col items-center justify-center h-full p-6 text-center" style={{ color: 'var(--danger)' }}>
                <PiWarningCircleBold className="text-5xl mb-4 opacity-50" />
                <h3 className="text-xl font-bold mb-2">Error</h3>
                <p className="max-w-md" style={{ color: 'var(--text-secondary)' }}>{error}</p>
            </div>
        );
    }

    return (
        <div className="max-w-4xl mx-auto h-full overflow-y-auto custom-scrollbar">
            <div className="pt-8 px-2">
            <div className="flex items-center gap-3 mb-8 pb-6" style={{ borderBottom: '1px solid var(--border)' }}>
                <div className="w-12 h-12 rounded-xl flex items-center justify-center text-2xl" style={{ background: 'var(--bg-accent-muted)', border: '1px solid color-mix(in srgb, var(--accent) 20%, transparent)', color: 'var(--accent)' }}>
                    <PiNotePencilBold />
                </div>
                <div>
                    <h1 className="text-2xl font-bold tracking-tight" style={{ color: 'var(--text-primary)' }}>Documentation</h1>
                </div>
            </div>

            <div className="glass-panel rounded-2xl p-8 relative overflow-hidden group" style={{ border: '1px solid var(--border)' }}>
                {/* Decorative Background Elements */}
                <div className="absolute top-0 right-0 w-64 h-64 blur-[100px] -mr-32 -mt-32 rounded-full" style={{ background: 'color-mix(in srgb, var(--accent) 5%, transparent)' }} />

                <div className="prose prose-invert max-w-none
                    prose-headings:font-bold prose-headings:tracking-tight
                    prose-h1:text-3xl prose-h1:mb-8
                    prose-h2:text-xl prose-h2:mt-10 prose-h2:mb-4 prose-h2:pb-2
                    prose-p:leading-relaxed prose-p:mb-6
                    prose-ul:list-disc prose-ul:ml-6 prose-ul:mb-6
                    prose-li:mb-2
                    prose-strong:font-bold
                    prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded prose-code:before:content-none prose-code:after:content-none
                    prose-blockquote:border-l-4 prose-blockquote:py-2 prose-blockquote:px-6 prose-blockquote:rounded-r-lg prose-blockquote:italic
                    prose-a:no-underline hover:prose-a:underline
                "
                style={{
                    '--tw-prose-headings': 'var(--text-primary)',
                    '--tw-prose-body': 'var(--text-primary)',
                    '--tw-prose-bold': 'var(--accent)',
                    '--tw-prose-links': 'var(--accent)',
                    '--tw-prose-code': 'var(--accent)',
                    '--tw-prose-quotes': 'var(--text-secondary)',
                    '--tw-prose-quote-borders': 'var(--accent)',
                }}
                >
                    <ReactMarkdown>{content}</ReactMarkdown>
                </div>
            </div>
            </div>
        </div>
    );
};

export default NotesPage;
