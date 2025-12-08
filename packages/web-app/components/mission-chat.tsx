'use client';

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Mission } from "@core/index";

interface MissionChatProps {
    mission: Mission;
}

export function MissionChat({ mission }: MissionChatProps) {
    const router = useRouter();
    const [messages, setMessages] = useState<Array<{ role: 'user' | 'assistant'; content: string }>>([]);
    const [input, setInput] = useState('');
    const [loading, setLoading] = useState(false);
    const [completed, setCompleted] = useState(false);
    const [score, setScore] = useState<number | null>(null);
    const [feedback, setFeedback] = useState<string | null>(null);

    useEffect(() => {
        // Send initial greeting
        setMessages([{
            role: 'assistant',
            content: `Hello! Welcome to the "${mission.title}" scenario. Let's begin!`,
        }]);
    }, [mission]);

    const handleSend = async () => {
        if (!input.trim()) return;

        const userMessage = input.trim();
        setInput('');
        setMessages(prev => [...prev, { role: 'user', content: userMessage }]);
        setLoading(true);

        try {
            // This would call the mission chat API
            // For now, we'll simulate a response
            await new Promise(resolve => setTimeout(resolve, 1000));

            const assistantResponse = 'Great! Continue practicing...';
            setMessages(prev => [...prev, { role: 'assistant', content: assistantResponse }]);
        } catch (error) {
            console.error('Failed to send message:', error);
        } finally {
            setLoading(false);
        }
    };

    const handleComplete = async () => {
        setLoading(true);
        try {
            // This would call the mission evaluation API
            await new Promise(resolve => setTimeout(resolve, 1500));

            setScore(85);
            setFeedback('Great job! You completed the mission successfully. Your grammar was good, and you used appropriate vocabulary for your level.');
            setCompleted(true);
        } catch (error) {
            console.error('Failed to complete mission:', error);
        } finally {
            setLoading(false);
        }
    };

    if (completed && score !== null && feedback) {
        return (
            <div className="container mx-auto px-4 py-10 max-w-2xl">
                <Card>
                    <CardHeader>
                        <CardTitle className="text-2xl text-center">Mission Complete!</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-6">
                        <div className="text-center">
                            <div className="text-6xl font-bold text-teal-600 mb-2">{score}</div>
                            <p className="text-neutral-600">out of 100</p>
                        </div>
                        <div className="bg-neutral-50 p-4 rounded-lg">
                            <h3 className="font-semibold mb-2">Feedback:</h3>
                            <p className="text-neutral-700">{feedback}</p>
                        </div>
                        <div className="flex gap-4">
                            <Button onClick={() => router.push('/missions')} className="flex-1">
                                Back to Missions
                            </Button>
                            <Button onClick={() => window.location.reload()} className="flex-1">
                                Try Again
                            </Button>
                        </div>
                    </CardContent>
                </Card>
            </div>
        );
    }

    return (
        <div className="container mx-auto px-4 py-10 max-w-4xl">
            <div className="mb-6">
                <h1 className="text-2xl font-bold mb-2">{mission.title}</h1>
                <p className="text-neutral-600 mb-4">{mission.scenario}</p>
                <div className="bg-teal-50 p-4 rounded-lg">
                    <h3 className="font-semibold text-sm mb-2">Objectives:</h3>
                    <ul className="text-sm space-y-1">
                        {mission.objectives.map((obj, idx) => (
                            <li key={idx} className="flex items-start">
                                <span className="mr-2">•</span>
                                <span>{obj}</span>
                            </li>
                        ))}
                    </ul>
                </div>
            </div>

            <Card className="mb-4">
                <CardContent className="p-4">
                    <div className="h-96 overflow-y-auto mb-4 space-y-4">
                        {messages.map((msg, idx) => (
                            <div
                                key={idx}
                                className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                            >
                                <div
                                    className={`max-w-[70%] rounded-lg p-3 ${msg.role === 'user'
                                        ? 'bg-teal-600 text-white'
                                        : 'bg-neutral-100 text-neutral-900'
                                        }`}
                                >
                                    {msg.content}
                                </div>
                            </div>
                        ))}
                        {loading && (
                            <div className="flex justify-start">
                                <div className="bg-neutral-100 rounded-lg p-3">
                                    <span className="text-neutral-600">Typing...</span>
                                </div>
                            </div>
                        )}
                    </div>

                    <div className="flex gap-2">
                        <input
                            type="text"
                            value={input}
                            onChange={(e) => setInput(e.target.value)}
                            onKeyPress={(e) => e.key === 'Enter' && handleSend()}
                            placeholder="Type your message..."
                            className="flex-1 rounded-md border border-neutral-200 p-2 text-sm"
                            disabled={loading}
                        />
                        <Button onClick={handleSend} disabled={loading || !input.trim()}>
                            Send
                        </Button>
                    </div>
                </CardContent>
            </Card>

            <div className="flex gap-4">
                <Button onClick={() => router.push('/missions')}>
                    Back
                </Button>
                <Button onClick={handleComplete} disabled={loading || messages.length < 4}>
                    Complete Mission
                </Button>
            </div>
        </div>
    );
}
