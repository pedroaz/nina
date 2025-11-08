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
        <Card>
            <CardHeader className="flex flex-row items-start justify-between gap-4">
                <div className="space-y-2">
                    <CardTitle className="text-base font-medium">
                        {title}
                    </CardTitle>
                    <div className="flex gap-2">
                        <Badge variant="secondary">
                            {cardCount} cards
                        </Badge>
                        {sourceLesson && (
                            <Badge variant="outline">From lesson</Badge>
                        )}
                    </div>
                </div>
                <Button
                    variant="destructive"
                    size="sm"
                    onClick={handleDelete}
                    disabled={isDeleting}
                >
                    {isDeleting ? 'Deleting...' : 'Delete'}
                </Button>
            </CardHeader>
            <CardContent className="flex flex-col gap-2 text-sm text-slate-600">
                <div className="flex items-center justify-between">
                    <span>Progress:</span>
                    <span className="font-medium">
                        {knownCards} / {totalCards} known
                    </span>
                </div>
                <div className="h-2 w-full overflow-hidden rounded-full bg-slate-200">
                    <div
                        className="h-full bg-green-500 transition-all"
                        style={{
                            width: `${totalCards > 0 ? (knownCards / totalCards) * 100 : 0}%`,
                        }}
                    />
                </div>
            </CardContent>
            <CardFooter className="flex justify-end">
                <Button asChild size="sm">
                    <Link href={`/flash-cards/${id}`}>Practice</Link>
                </Button>
            </CardFooter>
        </Card>
    );
}
