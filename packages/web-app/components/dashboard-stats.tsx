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
            value: stats?.lessonsCount || 0,
            icon: BookOpen,
            color: "text-orange-600",
            bgColor: "bg-orange-50",
        },
        {
            title: "Exercise Sets",
            value: stats?.exerciseSetsCount || 0,
            icon: Dumbbell,
            color: "text-teal-600",
            bgColor: "bg-teal-50",
        },
        {
            title: "Flashcard Decks",
            value: stats?.flashCardDecksCount || 0,
            icon: CreditCard,
            color: "text-orange-700",
            bgColor: "bg-orange-100",
        },
        {
            title: "Missions Completed",
            value: stats?.missionsCompleted || 0,
            icon: Target,
            color: "text-teal-700",
            bgColor: "bg-teal-100",
        },
    ];

    return (
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
            {statCards.map((stat, index) => {
                const Icon = stat.icon;
                const isOrange = index % 2 === 0;
                const cardClass = isOrange ? 'stat-card-orange' : 'stat-card-teal';
                return (
                    <div key={stat.title} className={`card-playful ${cardClass} p-6`}>
                        <div className="flex items-center justify-between mb-3">
                            <h3 className="text-sm font-bold text-neutral-900 uppercase tracking-wide">
                                {stat.title}
                            </h3>
                            <div className={`icon-bubble ${stat.bgColor === 'bg-orange-50' || stat.bgColor === 'bg-orange-100' ? 'bg-orange-200' : 'bg-teal-200'}`}>
                                <Icon className={`h-5 w-5 ${stat.color}`} />
                            </div>
                        </div>
                        <div className="text-4xl font-extrabold text-neutral-900">{stat.value}</div>
                    </div>
                );
            })}
        </div>
    );
}
