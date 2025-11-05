'use client';

import { useState, useRef, useEffect } from 'react';
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
import { SendIcon, Loader2 } from 'lucide-react';
import type { Lesson } from '@core/entities/lesson';

interface ChatMessage {
    role: 'user' | 'model';
    content: string;
}

interface AvatarChatPanelProps {
    isOpen: boolean;
    onClose: () => void;
    lesson?: Lesson;
}

export function AvatarChatPanel({ isOpen, onClose, lesson }: AvatarChatPanelProps) {
    const [message, setMessage] = useState('');
    const [messages, setMessages] = useState<ChatMessage[]>([]);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const messagesEndRef = useRef<HTMLDivElement>(null);

    // Auto-scroll to bottom when new messages arrive
    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages]);

    const handleSend = async () => {
        if (!message.trim() || isLoading) return;

        const userMessage = message.trim();
        setMessage('');
        setError(null);

        // Add user message to UI immediately
        const newUserMessage: ChatMessage = {
            role: 'user',
            content: userMessage,
        };
        setMessages((prev) => [...prev, newUserMessage]);
        setIsLoading(true);

        try {
            // Send to API
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    message: userMessage,
                    history: messages,
                    lessonContext: lesson,
                }),
            });

            if (!response.ok) {
                throw new Error('Failed to get response from Nina');
            }

            const data = await response.json();

            // Add Nina's response to messages
            const ninaMessage: ChatMessage = {
                role: 'model',
                content: data.response,
            };
            setMessages((prev) => [...prev, ninaMessage]);
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Something went wrong');
            console.error('Chat error:', err);
        } finally {
            setIsLoading(false);
        }
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
                    {messages.length === 0 && (
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
                                    Hallo! I&apos;m Nina, your German learning assistant.
                                    {lesson
                                        ? " I can help you understand this lesson and answer any questions you have about it."
                                        : " How can I help you with your German learning today?"
                                    }
                                </p>
                            </Card>
                        </div>
                    )}

                    {/* Display chat messages */}
                    {messages.map((msg, idx) => (
                        msg.role === 'user' ? (
                            <div key={idx} className="flex justify-end gap-3">
                                <Card className="max-w-[80%] bg-primary p-3 text-primary-foreground">
                                    <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
                                </Card>
                            </div>
                        ) : (
                            <div key={idx} className="flex gap-3">
                                <div className="h-8 w-8 flex-shrink-0 overflow-hidden rounded-full">
                                    <img
                                        src="/images/nina-head.png"
                                        alt="Nina"
                                        className="h-full w-full object-cover"
                                    />
                                </div>
                                <Card className="flex-1 bg-muted p-3">
                                    <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
                                </Card>
                            </div>
                        )
                    ))}

                    {/* Loading indicator */}
                    {isLoading && (
                        <div className="flex gap-3">
                            <div className="h-8 w-8 flex-shrink-0 overflow-hidden rounded-full">
                                <img
                                    src="/images/nina-head.png"
                                    alt="Nina"
                                    className="h-full w-full object-cover"
                                />
                            </div>
                            <Card className="flex-1 bg-muted p-3">
                                <div className="flex items-center gap-2">
                                    <Loader2 className="h-4 w-4 animate-spin" />
                                    <p className="text-sm text-muted-foreground">Nina is typing...</p>
                                </div>
                            </Card>
                        </div>
                    )}

                    {/* Error message */}
                    {error && (
                        <div className="rounded-md bg-destructive/10 p-3">
                            <p className="text-sm text-destructive">{error}</p>
                        </div>
                    )}

                    <div ref={messagesEndRef} />
                </div>

                {/* Input Area - Fixed at Bottom */}
                <div className="border-t bg-background p-4">
                    <div className="flex gap-2">
                        <Input
                            placeholder="Type your message..."
                            value={message}
                            onChange={(e) => setMessage(e.target.value)}
                            onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleSend()}
                            className="flex-1"
                            disabled={isLoading}
                        />
                        <Button
                            size="icon"
                            onClick={handleSend}
                            disabled={!message.trim() || isLoading}
                        >
                            <SendIcon className="h-4 w-4" />
                        </Button>
                    </div>
                </div>
            </SheetContent>
        </Sheet>
    );
}
