'use client';

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";

interface Mission {
    _id: string;
    title: string;
    scenario: string;
    difficulty: string;
    objectives: string[];
}

export default function MissionsPage() {
    const router = useRouter();
    const [missions, setMissions] = useState<Mission[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        // For now, use predefined missions
        // In the future, these could be fetched from an API or generated dynamically
        const predefinedMissions: Mission[] = [
            {
                _id: 'coffee-shop',
                title: 'Ordering Coffee',
                scenario: 'You are at a coffee shop and want to order a coffee.',
                difficulty: 'A1',
                objectives: ['Greet the barista', 'Order a coffee', 'Ask for the price', 'Say thank you'],
            },
            {
                _id: 'train-station',
                title: 'Buying a Train Ticket',
                scenario: 'You are at a train station and need to buy a ticket.',
                difficulty: 'A2',
                objectives: ['Ask for a ticket to a destination', 'Specify the time', 'Pay for the ticket'],
            },
            {
                _id: 'restaurant',
                title: 'Dining at a Restaurant',
                scenario: 'You are at a restaurant and want to order food.',
                difficulty: 'B1',
                objectives: ['Ask for the menu', 'Order food and drinks', 'Ask about ingredients', 'Request the bill'],
            },
        ];
        setMissions(predefinedMissions);
        setLoading(false);
    }, []);

    if (loading) {
        return (
            <div className="flex min-h-screen items-center justify-center">
                <p className="text-slate-600">Loading missions...</p>
            </div>
        );
    }

    return (
        <div className="container mx-auto px-4 py-10">
            <div className="mb-8">
                <h1 className="text-3xl font-bold mb-2">Language Missions</h1>
                <p className="text-slate-600">
                    Practice real-world scenarios and improve your conversation skills.
                </p>
            </div>

            <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
                {missions.map((mission) => (
                    <Card key={mission._id} className="hover:shadow-lg transition-shadow">
                        <CardHeader>
                            <div className="flex items-center justify-between mb-2">
                                <CardTitle className="text-xl">{mission.title}</CardTitle>
                                <span className="px-2 py-1 text-xs font-semibold rounded bg-blue-100 text-blue-700">
                                    {mission.difficulty}
                                </span>
                            </div>
                            <CardDescription>{mission.scenario}</CardDescription>
                        </CardHeader>
                        <CardContent>
                            <div className="mb-4">
                                <h4 className="text-sm font-semibold mb-2">Objectives:</h4>
                                <ul className="text-sm text-slate-600 space-y-1">
                                    {mission.objectives.map((obj, idx) => (
                                        <li key={idx} className="flex items-start">
                                            <span className="mr-2">•</span>
                                            <span>{obj}</span>
                                        </li>
                                    ))}
                                </ul>
                            </div>
                            <Button
                                onClick={() => router.push(`/missions/${mission._id}`)}
                                className="w-full"
                            >
                                Start Mission
                            </Button>
                        </CardContent>
                    </Card>
                ))}
            </div>
        </div>
    );
}
