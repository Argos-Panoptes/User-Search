import { useState, useEffect } from 'react';
import apiClient from '../services/api';

const useMediaUrl = (mediaId, initialUrl = null) => {
    const [url, setUrl] = useState(initialUrl);
    const [loading, setLoading] = useState(!initialUrl && !!mediaId);
    const [error, setError] = useState(false);

    useEffect(() => {
        let isMounted = true;

        const fetchMediaUrl = async () => {
            // If we already have a valid HTTP URL (e.g. external link) or no mediaId, don't fetch.

            if (!mediaId) {
                setUrl(initialUrl || null);
                if (!initialUrl) setLoading(false);
                return;
            }

            // If initialUrl is already an http link, use it and don't fetch.
            if (initialUrl && initialUrl.startsWith('http')) {
                setUrl(initialUrl);
                setLoading(false);
                return;
            }

            try {
                setLoading(true);
                setError(false);
                const response = await apiClient.get(`/media/${mediaId}/download`);
                if (isMounted) {
                    if (response.data && response.data.url) {
                        setUrl(response.data.url);
                    } else {
                        console.error('Invalid media response format:', response.data);
                        setError(true);
                    }
                }
            } catch (err) {
                if (isMounted) {
                    console.error(`Failed to fetch media URL for ID ${mediaId}:`, err);
                    setError(true);
                }
            } finally {
                if (isMounted) {
                    setLoading(false);
                }
            }
        };

        fetchMediaUrl();

        return () => {
            isMounted = false;
        };
    }, [mediaId, initialUrl]);

    return { url, loading, error };
};

export default useMediaUrl;
