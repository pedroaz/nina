'use client';

import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { BookOpen, Dumbbell, CreditCard, Target } from "lucide-react";

interface DashboardStatsProps {
    userId: string;
}

interface Stats {
    lessonsCount: number;
    exerciseSetsCount: number;
    flashCardDecksCount: number;
    missionsCompleted: number;
}

export function DashboardStats({ userId }: DashboardStatsProps) {
    const [stats, setStats] = useState<Stats | null>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchStats = async () => {
            try {
                const response = await fetch('/api/user/stats');
                if (response.ok) {
                    const data = await response.json();
                    setStats(data);
                }
            } catch (error) {
                console.error('Failed to fetch stats:', error);
            } finally {
                setLoading(false);
            }
        };

        fetchStats();
    }, [userId]);

    if (loading) {
        return (
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
                {[...Array(4)].map((_, i) => (
                    <Card key={i}>
                        <CardContent className="p-6">
                            <div className="h-20 animate-pulse bg-neutral-100 rounded"></div>
                        </CardContent>
                    </Card>
                ))}
            </div>
        );
    }

    const statCards = [
        {
            title: "Lessons",
            value: stats?.lessonsCount ?? 0,
            icon: BookOpen,
        },
        {
            title: "Exercise Sets",
            value: stats?.exerciseSetsCount ?? 0,
            icon: Dumbbell,
        },
        {
            title: "Flashcard Decks",
            value: stats?.flashCardDecksCount ?? 0,
            icon: CreditCard,
        },
        {
            title: "Missions Completed",
            value: stats?.missionsCompleted ?? 0,
            icon: Target,
        },
    ];

    return (
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
            {statCards.map((stat, index) => {
                const Icon = stat.icon;
                const isPrimary = index % 2 === 0;
                const iconColor = isPrimary ? 'text-orange-500' : 'text-teal-500';

                return (
                    <Card key={stat.title}>
                        <CardHeader>
                            <CardTitle className="flex items-center justify-between">
                                <span className="text-sm">{stat.title}</span>
                                <Icon className={`h-6 w-6 ${iconColor}`} />
                            </CardTitle>
                        </CardHeader>
                        <CardContent>
                            <div className="text-3xl font-bold">{stat.value}</div>
                        </CardContent>
                    </Card>
                );
            })}
        </div>
    );
}
