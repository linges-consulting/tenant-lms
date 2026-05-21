import React from 'react';
import { FileQuestion, Home } from 'lucide-react';
import { Button } from '../components/ui/button';
import { useNavigate } from 'react-router-dom';

export const NotFound: React.FC = () => {
    const navigate = useNavigate();

    return (
        <div className="flex-1 flex flex-col items-center justify-center min-h-[60vh] text-center px-4">
            <div className="bg-muted w-24 h-24 rounded-full flex items-center justify-center mb-6">
                <FileQuestion className="w-12 h-12 text-muted-foreground" />
            </div>

            <h1 className="text-6xl font-black text-foreground mb-4 tracking-tight">404</h1>
            <h2 className="text-2xl font-semibold text-foreground mb-2">Page Not Found</h2>
            <p className="text-muted-foreground max-w-md mx-auto mb-8">
                We couldn't find the page you were looking for. It might have been removed, renamed, or didn't exist in the first place.
            </p>

            <div className="flex gap-4 items-center">
                <Button
                    variant="outline"
                    onClick={() => navigate(-1)}
                >
                    Go Back
                </Button>
                <Button
                    onClick={() => navigate('/dashboard')}
                    className="flex text-white items-center gap-2"
                >
                    <Home className="w-4 h-4" />
                    Back to Dashboard
                </Button>
            </div>
        </div>
    );
};
