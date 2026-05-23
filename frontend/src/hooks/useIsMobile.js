import { useEffect, useState } from 'react';

const MOBILE_MEDIA_QUERY = '(max-width: 767px)';

export default function useIsMobile() {
    const [isMobile, setIsMobile] = useState(() => {
        if (typeof window === 'undefined') {
            return false;
        }
        return window.matchMedia(MOBILE_MEDIA_QUERY).matches;
    });

    useEffect(() => {
        const mediaQueryList = window.matchMedia(MOBILE_MEDIA_QUERY);
        const updateViewport = (event) => setIsMobile(event.matches);

        setIsMobile(mediaQueryList.matches);
        mediaQueryList.addEventListener('change', updateViewport);

        return () => mediaQueryList.removeEventListener('change', updateViewport);
    }, []);

    return isMobile;
}
