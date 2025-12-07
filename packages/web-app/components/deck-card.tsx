"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import {
    Card,
    CardContent,
    CardFooter,
    CardHeader,
    CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

type DeckCardProps = {
    id: string;
    title: string;
    cardCount: number;
    knownCards: number;
    totalCards: number;
    sourceLesson?: string;
};

export function DeckCard({ id, title, cardCount, knownCards, totalCards, sourceLesson }: DeckCardProps) {
    const router = useRouter();
    const [isDeleting, setIsDeleting] = useState(false);

    const handleDelete = async () => {
        if (!confirm(`Are you sure you want to delete "${title}"?`)) {
            return;
        }

        setIsDeleting(true);

        try {
            const response = await fetch(`/api/flash-cards/${id}`, {
                method: 'DELETE',
            });

            if (!response.ok) {
                throw new Error('Failed to delete deck');
            }

            router.refresh();
        } catch (error) {
            console.error('Error deleting deck:', error);
            alert('Failed to delete deck. Please try again.');
            setIsDeleting(false);
        }
    };

    return (
        <div className="card-playful bg-white p-5">
            <div className="flex items-start justify-between gap-4 mb-4">
                <div className="space-y-2 flex-1">
                    <h3 className="text-lg font-extrabold text-neutral-900">
                        {title}
                    </h3>
                    <div className="flex gap-2">
                        <span className="badge-playful bg-teal-100 text-teal-700">
                            📚 {cardCount} cards
                        </span>
                        {sourceLesson && (
                            <span className="badge-playful bg-orange-100 text-orange-700">📖 From lesson</span>
                        )}
                    </div>
                </div>
                <button
                    className="btn-playful bg-error-bg border-error-text text-error-text hover:bg-error/10 px-3 py-1.5 text-sm"
                    onClick={handleDelete}
                    disabled={isDeleting}
                >
                    {isDeleting ? '⏳' : '🗑️'}
                </button>
            </div>
            <div className="flex flex-col gap-2 text-sm text-neutral-700 mb-4">
                <div className="flex items-center justify-between font-bold">
                    <span>Progress:</span>
                    <span>
                        {knownCards} / {totalCards} known
                    </span>
                </div>
                <div className="progress-playful bg-neutral-100">
                    <div
                        className="progress-fill-playful bg-success"
                        style={{
                            width: `${totalCards > 0 ? (knownCards / totalCards) * 100 : 0}%`,
                        }}
                    />
                </div>
            </div>
            <Link href={`/flash-cards/${id}`} className="block">
                <button className="btn-playful btn-primary-playful w-full py-2.5 text-base">
                    🎯 Practice Now
                </button>
            </Link>
        </div>
    );
}
