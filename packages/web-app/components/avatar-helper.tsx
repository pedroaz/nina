'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Tooltip, TooltipContent, TooltipTrigger, TooltipProvider } from '@/components/ui/tooltip';
import { AvatarChatPanel } from './avatar-chat-panel';
import type { Lesson } from '@core/entities/lesson';

interface AvatarHelperProps {
    lesson?: Lesson;
}

export function AvatarHelper({ lesson }: AvatarHelperProps) {
    const [isOpen, setIsOpen] = useState(false);

    return (
        <>
            {/* Floating Avatar Button */}
            <TooltipProvider>
                <Tooltip>
                    <TooltipTrigger asChild>
                        <Button
                            onClick={() => setIsOpen(true)}
                            size="lg"
                            className="fixed bottom-6 right-6 z-50 h-16 w-16 p-0 rounded-full border-2 border-primary/20 shadow-xl transition-all duration-200 hover:scale-110 active:scale-95"
                            aria-label="Open chat with Nina"
                        >
                            <img
                                src="/images/nina-head.png"
                                alt="Nina avatar"
                                className="h-full w-full object-cover rounded-full"
                            />
                        </Button>
                    </TooltipTrigger>
                    <TooltipContent side="left">Chat with Nina</TooltipContent>
                </Tooltip>
            </TooltipProvider>

            {/* Chat Panel */}
            <AvatarChatPanel isOpen={isOpen} onClose={() => setIsOpen(false)} lesson={lesson} />
        </>
    );
}
