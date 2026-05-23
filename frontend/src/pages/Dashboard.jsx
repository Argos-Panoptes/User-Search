import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import UserSearch from '../features/UserSearch';
import GroupSearch from '../features/GroupSearch';

const Dashboard = () => {
    const { user, logout } = useAuth();
    const [activeTab, setActiveTab] = useState('users'); // 'users' or 'groups'

    const [userSearchInitialState, setUserSearchInitialState] = useState(null);

    const handleViewMembers = (groupName) => {
        setUserSearchInitialState({ groupName });
        setActiveTab('users');
    };

    return (
        <div className="min-h-screen font-sans" style={{ background: 'var(--bg-page)', color: 'var(--text-primary)' }}>
            {/* Navbar */}
            {/* ... */}

            {/* Main Content */}
            <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
                {/* Tabs */}
                {/* ... */}

                {/* Tab Content */}
                <div className="animate-fade-in">
                    {activeTab === 'users' ? (
                        <UserSearch initialState={userSearchInitialState} />
                    ) : (
                        <GroupSearch onViewMembers={handleViewMembers} />
                    )}
                </div>
            </main>
        </div>
    );
};

export default Dashboard;
