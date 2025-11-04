'use client';

import { useState } from 'react';
import { Tooltip, TooltipContent, TooltipTrigger, TooltipProvider } from '@/components/ui/tooltip';
import { AvatarChatPanel } from './avatar-chat-panel';

export function AvatarHelper() {
    const [isOpen, setIsOpen] = useState(false);

    return (
        <>
            {/* Floating Avatar Button */}
            <TooltipProvider>
                <Tooltip>
                    <TooltipTrigger asChild>
                        <button
                            onClick={() => setIsOpen(true)}
                            className="fixed bottom-6 right-6 z-50 h-16 w-16 overflow-hidden rounded-full border-2 border-primary/20 bg-white shadow-xl transition-all duration-200 hover:scale-110 active:scale-95 focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                            aria-label="Open chat with Nina"
                        >
                            <img
                                src="/images/nina-head.png"
                                alt="Nina avatar"
                                className="h-full w-full object-cover"
                            />
                        </button>
                    </TooltipTrigger>
                    <TooltipContent side="left">Chat with Nina</TooltipContent>
                </Tooltip>
            </TooltipProvider>

            {/* Chat Panel */}
            <AvatarChatPanel isOpen={isOpen} onClose={() => setIsOpen(false)} />
        </>
    );
}
