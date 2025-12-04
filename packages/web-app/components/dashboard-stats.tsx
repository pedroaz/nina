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
                            <div className="h-20 animate-pulse bg-slate-100 rounded"></div>
                        </CardContent>
                    </Card>
                ))}
            </div>
        );
    }

    const statCards = [
        {
            title: "Lessons",
            value: stats?.lessonsCount || 0,
            icon: BookOpen,
            color: "text-blue-600",
            bgColor: "bg-blue-50",
        },
        {
            title: "Exercise Sets",
            value: stats?.exerciseSetsCount || 0,
            icon: Dumbbell,
            color: "text-green-600",
            bgColor: "bg-green-50",
        },
        {
            title: "Flashcard Decks",
            value: stats?.flashCardDecksCount || 0,
            icon: CreditCard,
            color: "text-purple-600",
            bgColor: "bg-purple-50",
        },
        {
            title: "Missions Completed",
            value: stats?.missionsCompleted || 0,
            icon: Target,
            color: "text-orange-600",
            bgColor: "bg-orange-50",
        },
    ];

    return (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            {statCards.map((stat) => {
                const Icon = stat.icon;
                return (
                    <Card key={stat.title}>
                        <CardHeader className="flex flex-row items-center justify-between pb-2">
                            <CardTitle className="text-sm font-medium text-slate-600">
                                {stat.title}
                            </CardTitle>
                            <div className={`p-2 rounded-lg ${stat.bgColor}`}>
                                <Icon className={`h-4 w-4 ${stat.color}`} />
                            </div>
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
