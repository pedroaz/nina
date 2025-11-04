'use client';

import { useState } from 'react';
import {
    Sheet,
    SheetContent,
    SheetHeader,
    SheetTitle,
    SheetDescription,
} from '@/components/ui/sheet';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card } from '@/components/ui/card';
import { SendIcon } from 'lucide-react';

interface AvatarChatPanelProps {
    isOpen: boolean;
    onClose: () => void;
}

export function AvatarChatPanel({ isOpen, onClose }: AvatarChatPanelProps) {
    const [message, setMessage] = useState('');

    const handleSend = () => {
        // Placeholder - no actual functionality
        if (!message.trim()) return;
        console.log('Message sent:', message);
        setMessage('');
    };

    return (
        <Sheet open={isOpen} onOpenChange={onClose}>
            <SheetContent
                side="right"
                className="flex w-full flex-col p-0 sm:max-w-md md:max-w-lg"
            >
                <SheetHeader className="border-b p-6">
                    <div className="flex items-center gap-3">
                        <div className="h-10 w-10 overflow-hidden rounded-full">
                            <img
                                src="/images/nina-head.png"
                                alt="Nina"
                                className="h-full w-full object-cover"
                            />
                        </div>
                        <div>
                            <SheetTitle>Nina</SheetTitle>
                            <SheetDescription>Your German learning assistant</SheetDescription>
                        </div>
                    </div>
                </SheetHeader>

                {/* Messages Area - Scrollable */}
                <div className="flex-1 space-y-4 overflow-y-auto p-6">
                    {/* Welcome message from Nina */}
                    <div className="flex gap-3">
                        <div className="h-8 w-8 flex-shrink-0 overflow-hidden rounded-full">
                            <img
                                src="/images/nina-head.png"
                                alt="Nina"
                                className="h-full w-full object-cover"
                            />
                        </div>
                        <Card className="flex-1 bg-muted p-3">
                            <p className="text-sm">
                                Hallo! I&apos;m Nina, your German learning assistant. How can I help
                                you today?
                            </p>
                        </Card>
                    </div>

                    {/* Example user message */}
                    <div className="flex justify-end gap-3">
                        <Card className="max-w-[80%] bg-primary p-3 text-primary-foreground">
                            <p className="text-sm">Can you help me with German grammar?</p>
                        </Card>
                    </div>

                    {/* Example Nina response */}
                    <div className="flex gap-3">
                        <div className="h-8 w-8 flex-shrink-0 overflow-hidden rounded-full">
                            <img
                                src="/images/nina-head.png"
                                alt="Nina"
                                className="h-full w-full object-cover"
                            />
                        </div>
                        <Card className="flex-1 bg-muted p-3">
                            <p className="text-sm">
                                Of course! I&apos;d be happy to help. What grammar topic would you
                                like to learn about?
                            </p>
                        </Card>
                    </div>
                </div>

                {/* Input Area - Fixed at Bottom */}
                <div className="border-t bg-background p-4">
                    <div className="flex gap-2">
                        <Input
                            placeholder="Type your message..."
                            value={message}
                            onChange={(e) => setMessage(e.target.value)}
                            onKeyDown={(e) => e.key === 'Enter' && handleSend()}
                            className="flex-1"
                        />
                        <Button size="icon" onClick={handleSend} disabled={!message.trim()}>
                            <SendIcon className="h-4 w-4" />
                        </Button>
                    </div>
                </div>
            </SheetContent>
        </Sheet>
    );
}
