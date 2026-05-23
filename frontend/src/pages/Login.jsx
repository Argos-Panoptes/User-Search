import React, { useState } from 'react';
import { Navigate } from 'react-router';
import { authClient } from '../services/authClient';
import { useAuth } from '../context/AuthContext';
import {
    PiShieldCheckBold,
    PiEnvelopeSimpleBold,
    PiArrowRightBold,
    PiSpinnerGapBold,
    PiCheckCircleFill,
    PiWarningCircleBold
} from "react-icons/pi";

const Login = () => {
    const { isAuthenticated } = useAuth();
    const [email, setEmail] = useState('');
    const [loading, setLoading] = useState(false);
    const [sent, setSent] = useState(false);
    const [error, setError] = useState('');

    // Redirect if already logged in
    if (isAuthenticated) {
        return <Navigate to="/app/users" replace />;
    }

    const handleLogin = async (e) => {
        e.preventDefault();
        setLoading(true);
        setError('');

        try {
            const { data, error } = await authClient.signIn.magicLink({
                email: email,
            });

            if (error) {
                setError(error.message || 'Failed to send magic link');
            } else {
                setSent(true);
            }
        } catch (err) {
            setError('An unexpected error occurred. Please try again.');
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="min-h-screen flex flex-col items-center justify-center relative overflow-hidden p-6" style={{ background: 'var(--bg-page)' }}>
            {/* Background Decor */}
            <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-full max-w-4xl h-full pointer-events-none opacity-20">
                <div className="absolute top-0 left-1/4 w-96 h-96 blur-[150px] rounded-full mix-blend-screen animate-pulse-slow" style={{ background: 'var(--accent)' }} />
                <div className="absolute bottom-0 right-1/4 w-96 h-96 blur-[150px] rounded-full mix-blend-screen animate-pulse-slow" style={{ background: 'var(--accent)', animationDelay: '1.5s' }} />
            </div>

            <div className="w-full max-w-md relative z-10">
                <div className="glass-panel rounded-3xl p-8 md:p-10 shadow-2xl backdrop-blur-xl" style={{ background: 'color-mix(in srgb, var(--bg-card) 40%, transparent)', borderColor: 'var(--border)' }}>
                    <div className="flex flex-col items-center mb-8 text-center">
                        <div className="w-16 h-16 rounded-2xl flex items-center justify-center shadow-glow mb-6 group transition-transform hover:scale-105 duration-500" style={{ background: 'linear-gradient(to bottom right, var(--accent), var(--accent-hover))', color: 'var(--text-on-accent)' }}>
                            <PiShieldCheckBold className="text-3xl" />
                        </div>
                        <h2 className="text-3xl font-bold tracking-tight" style={{ color: 'var(--text-primary)' }}>Welcome Back</h2>
                        <p className="mt-2 text-sm leading-relaxed max-w-xs" style={{ color: 'var(--text-secondary)' }}>
                            Sign in to access your intelligence dashboard.
                        </p>
                    </div>

                    {sent ? (
                        <div className="p-6 rounded-2xl text-center animate-in fade-in zoom-in duration-300" style={{ background: 'var(--success-bg)', border: '1px solid color-mix(in srgb, var(--success) 20%, transparent)' }}>
                            <div className="w-12 h-12 rounded-full flex items-center justify-center mx-auto mb-3" style={{ background: 'var(--success-bg)', color: 'var(--success)' }}>
                                <PiCheckCircleFill className="text-2xl" />
                            </div>
                            <h3 className="font-bold mb-1" style={{ color: 'var(--success)' }}>Magic Link Sent!</h3>
                            <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                                Check your inbox at <span className="font-medium" style={{ color: 'var(--text-primary)' }}>{email}</span> to sign in.
                            </p>
                            <button
                                onClick={() => setSent(false)}
                                className="mt-4 text-xs transition-colors font-medium"
                                style={{ color: 'var(--text-tertiary)' }}
                                onMouseEnter={(e) => e.currentTarget.style.color = 'var(--text-primary)'}
                                onMouseLeave={(e) => e.currentTarget.style.color = 'var(--text-tertiary)'}
                            >
                                Use a different email
                            </button>
                        </div>
                    ) : (
                        <form onSubmit={handleLogin} className="space-y-6">
                            <div className="space-y-2">
                                <label className="block text-xs font-bold uppercase tracking-widest pl-1" style={{ color: 'var(--text-tertiary)' }}>Email Address</label>
                                <div className="relative group">
                                    <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                                        <PiEnvelopeSimpleBold className="text-lg transition-colors" style={{ color: 'var(--text-tertiary)' }} />
                                    </div>
                                    <input
                                        type="email"
                                        required
                                        value={email}
                                        onChange={(e) => setEmail(e.target.value)}
                                        className="block w-full pl-11 pr-4 py-3.5 rounded-xl font-medium focus:outline-none focus:ring-2 transition-all"
                                        style={{ background: 'var(--bg-page)', border: '1px solid var(--border)', color: 'var(--text-primary)', '--tw-ring-color': 'color-mix(in srgb, var(--accent) 50%, transparent)' }}
                                        placeholder="name@company.com"
                                    />
                                </div>
                            </div>

                            {error && (
                                <div className="flex items-center gap-3 p-4 rounded-xl text-sm font-medium animate-in fade-in slide-in-from-top-2" style={{ background: 'var(--danger-bg)', border: '1px solid color-mix(in srgb, var(--danger) 20%, transparent)', color: 'var(--danger)' }}>
                                    <PiWarningCircleBold className="text-xl flex-shrink-0" />
                                    <p>{error}</p>
                                </div>
                            )}

                            <button
                                type="submit"
                                disabled={loading}
                                className="w-full h-12 relative overflow-hidden rounded-xl font-bold text-sm transition-all shadow-glow active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed group flex items-center justify-center gap-2"
                                style={{ background: 'linear-gradient(to right, var(--accent), var(--accent-hover))', color: 'var(--text-on-accent)' }}
                            >
                                {loading ? (
                                    <PiSpinnerGapBold className="text-xl animate-spin" />
                                ) : (
                                    <>
                                        <span>Send Magic Link</span>
                                        <PiArrowRightBold className="group-hover:translate-x-1 transition-transform" />
                                    </>
                                )}
                            </button>
                        </form>
                    )}
                </div>

                <p className="mt-8 text-center text-xs font-medium" style={{ color: 'var(--text-tertiary)' }}>
                    &copy; {new Date().getFullYear()} Signal Intelligence. Secure Access.
                </p>
            </div>
        </div>
    );
};

export default Login;
