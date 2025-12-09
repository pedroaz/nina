'use client';

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
    DialogTrigger,
} from "@/components/ui/dialog";
import { Home, User, BookOpen, Users, Map, CreditCard, Dumbbell, Target } from "lucide-react";

interface GenerateFlashCardsDialogProps {
    lessonId: string;
    lessonTitle: string;
}

export function GenerateFlashCardsDialog({ lessonId, lessonTitle }: GenerateFlashCardsDialogProps) {
    const router = useRouter();
    const [open, setOpen] = useState(false);
    const [deckTitle, setDeckTitle] = useState(lessonTitle);
    const [cardCount, setCardCount] = useState(10);
    const [isGenerating, setIsGenerating] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const handleGenerate = async () => {
        if (!deckTitle.trim()) {
            setError("Please provide a deck title.");
            return;
        }

        setIsGenerating(true);
        setError(null);

        try {
            const response = await fetch("/api/flash-cards", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    type: 'from-lesson',
                    lessonId,
                    deckTitle: deckTitle.trim(),
                    cardCount,
                }),
            });

            if (!response.ok) {
                const payload = await response.json().catch(() => null);
                const message =
                    typeof payload?.error === "string"
                        ? payload.error
                        : "Failed to generate flash cards.";
                throw new Error(message);
            }

            const deck = await response.json();

            // Close dialog and redirect to new deck
            setOpen(false);
            router.push(`/flash-cards/${deck._id}`);
            router.refresh();
        } catch (err) {
            const message = err instanceof Error ? err.message : "Something went wrong.";
            setError(message);
        } finally {
            setIsGenerating(false);
        }
    };

    return (
        <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
                <Button size="icon" variant="secondary">
                    <CreditCard></CreditCard>
                </Button>
            </DialogTrigger>
            <DialogContent className="sm:max-w-[425px]">
                <DialogHeader>
                    <DialogTitle>Generate Flash Cards from Lesson</DialogTitle>
                    <DialogDescription>
                        Create a deck of flash cards based on this lesson&apos;s content.
                    </DialogDescription>
                </DialogHeader>
                <div className="grid gap-4 py-4">
                    <div className="grid gap-2">
                        <Label htmlFor="deckTitle">Deck title</Label>
                        <Input
                            id="deckTitle"
                            value={deckTitle}
                            onChange={(e) => setDeckTitle(e.target.value)}
                            disabled={isGenerating}
                        />
                    </div>
                    <div className="grid gap-2">
                        <Label htmlFor="cardCount">Number of cards</Label>
                        <select
                            id="cardCount"
                            value={cardCount}
                            onChange={(e) => setCardCount(parseInt(e.target.value))}
                            className="w-full rounded-md border border-neutral-200 bg-white p-2 text-sm shadow-sm focus:border-neutral-300 focus:outline-none focus:ring-2 focus:ring-neutral-200"
                            disabled={isGenerating}
                        >
                            <option value={5}>5 cards</option>
                            <option value={10}>10 cards</option>
                            <option value={15}>15 cards</option>
                            <option value={20}>20 cards</option>
                        </select>
                    </div>
                    {error && (
                        <p className="text-sm text-error-text" role="alert">
                            {error}
                        </p>
                    )}
                    {isGenerating && (
                        <div className="rounded-lg bg-teal-50 p-3 border border-teal-200">
                            <p className="text-sm text-teal-900">
                                Generating flash cards...
                            </p>
                        </div>
                    )}
                </div>
                <DialogFooter>
                    <Button
                        type="button"
                        onClick={() => setOpen(false)}
                        disabled={isGenerating}
                    >
                        Cancel
                    </Button>
                    <Button onClick={handleGenerate} disabled={isGenerating}>
                        {isGenerating ? "Generating..." : "Generate"}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}
