import React from 'react';
import { ImSpinner8 } from 'react-icons/im';

const Spinner = ({ size = "md", className = "" }) => {
    const sizeClasses = {
        sm: "w-4 h-4",
        md: "w-8 h-8",
        lg: "w-12 h-12"
    };

    return (
        <ImSpinner8
            className={`animate-spin text-blue-500 ${sizeClasses[size] || sizeClasses.md} ${className}`}
        />
    );
};

export default Spinner;
