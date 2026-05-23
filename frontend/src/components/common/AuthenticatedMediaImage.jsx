import { PiImageBrokenBold } from 'react-icons/pi';
import Spinner from '../common/Spinner';
import useMediaUrl from '../../hooks/useMediaUrl';
import { useEffect, useState } from 'react';

const AuthenticatedMediaImage = ({
    mediaId,
    initialUrl,
    alt,
    className,
    fallbackIcon = <PiImageBrokenBold className="w-8 h-8" style={{ color: 'var(--text-tertiary)' }} />,
    ...props
}) => {
    const [imageLoadError, setImageLoadError] = useState(false);

    useEffect(() => {
        setImageLoadError(false);
    }, [mediaId, initialUrl]);


    // If we have an external URL, use it directly. Otherwise, fetch.
    const isExternal = initialUrl?.startsWith('http');
    const { url: fetchedUrl, loading, error } = useMediaUrl(!isExternal && mediaId ? mediaId : null);

    const imageUrl = isExternal ? initialUrl : fetchedUrl;

    if (loading && !isExternal) {
        return (
            <div className={`flex items-center justify-center ${className}`} style={{ background: 'var(--bg-card)' }}>
                <Spinner size="sm" />
            </div>
        );
    }

    if ((!isExternal && error) || !imageUrl || imageLoadError) {
        return (
            <div className={`flex items-center justify-center ${className}`} style={{ background: 'var(--bg-card)' }}>
                {fallbackIcon}
            </div>
        );
    }

    return (
        <img
            src={imageUrl}
            alt={alt}
            className={className}
            onError={() => setImageLoadError(true)}
            {...props}
        />
    );
};

export default AuthenticatedMediaImage;
