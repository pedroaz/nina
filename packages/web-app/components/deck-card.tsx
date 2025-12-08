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
import { Progress } from "@/components/ui/progress";
import { Book, BookOpen, Loader2, Target, Trash2 } from "lucide-react";

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
        <Card className="bg-white p-5">
            <div className="flex items-start justify-between gap-4 mb-4">
                <div className="space-y-2 flex-1">
                    <h3 className="text-lg font-extrabold text-neutral-900">
                        {title}
                    </h3>
                    <div className="flex gap-2">
                        <Badge variant="teal">
                            <Book className="mr-1 size-3" /> {cardCount} cards
                        </Badge>
                        {sourceLesson && (
                            <Badge variant="orange">
                                <BookOpen className="mr-1 size-3" /> From lesson
                            </Badge>
                        )}
                    </div>
                </div>
                <Button
                    variant="destructive"
                    size="sm"
                    className="px-3"
                    onClick={handleDelete}
                    disabled={isDeleting}
                >
                    {isDeleting ? <Loader2 className="size-4 animate-spin" /> : <Trash2 className="size-4" />}
                </Button>
            </div>
            <div className="flex flex-col gap-2 text-sm text-neutral-700 mb-4">
                <div className="flex items-center justify-between font-bold">
                    <span>Progress:</span>
                    <span>
                        {knownCards} / {totalCards} known
                    </span>
                </div>
                <Progress value={totalCards > 0 ? (knownCards / totalCards) * 100 : 0} />
            </div>
            <Link href={`/flash-cards/${id}`} className="block">
                <Button className="w-full py-6 text-base">
                    <Target className="mr-2 size-5" /> Practice Now
                </Button>
            </Link>
        </Card>
    );
}
