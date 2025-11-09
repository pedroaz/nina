'use client';

import { FormEvent, useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";

export default function NewFlashCardDeck() {
    const router = useRouter();
    const [topic, setTopic] = useState("");
    const [cardCount, setCardCount] = useState(10);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [elapsedSeconds, setElapsedSeconds] = useState(0);

    useEffect(() => {
        let interval: NodeJS.Timeout | null = null;

        if (isSubmitting) {
            setElapsedSeconds(0);
            interval = setInterval(() => {
                setElapsedSeconds(prev => prev + 1);
            }, 1000);
        } else {
            setElapsedSeconds(0);
        }

        return () => {
            if (interval) {
                clearInterval(interval);
            }
        };
    }, [isSubmitting]);

    const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
        event.preventDefault();

        const sanitizedTopic = topic.trim();

        if (!sanitizedTopic) {
            setError("Please provide a topic for your flash card deck.");
            return;
        }

        setIsSubmitting(true);
        setError(null);

        try {
            const requestBody = {
                type: 'from-prompt',
                topic: sanitizedTopic,
                cardCount: cardCount,
            };

            const response = await fetch("/api/flash-cards", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(requestBody),
            });

            if (response.status === 401) {
                router.push(
                    `/api/auth/signin?callbackUrl=${encodeURIComponent("/flash-cards/new")}`,
                );
                return;
            }

            if (!response.ok) {
                const payload = await response.json().catch(() => null);
                const message =
                    typeof payload?.error === "string"
                        ? payload.error
                        : "Unable to create your flash card deck.";
                throw new Error(message);
            }

            const deck = await response.json();

            setTopic("");
            setCardCount(10);
            router.push(`/flash-cards/${deck._id}`);
            router.refresh();
        } catch (err) {
            const message = err instanceof Error ? err.message : "Something went wrong.";
            setError(message);
        } finally {
            setIsSubmitting(false);
        }
    };

    return (
        <section className="flex min-h-[60vh] items-center justify-center px-4 py-10">
            <form
                onSubmit={handleSubmit}
                className="flex w-full max-w-2xl flex-col gap-6 rounded-xl border border-slate-200 bg-white p-8 shadow-sm"
            >
                <div className="flex flex-col gap-2">
                    <h1 className="text-2xl font-semibold">Create Flash Card Deck</h1>
                    <p className="text-sm text-slate-600">
                        Generate a deck of flash cards on any topic to practice Language vocabulary and phrases.
                    </p>
                </div>

                <div className="flex flex-col gap-2">
                    <Label htmlFor="topic">Deck topic</Label>
                    <textarea
                        id="topic"
                        name="topic"
                        value={topic}
                        onChange={(event) => setTopic(event.target.value)}
                        className="min-h-32 w-full rounded-md border border-slate-200 bg-white p-3 text-sm shadow-sm focus:border-slate-400 focus:outline-none focus:ring-2 focus:ring-slate-200"
                        placeholder="e.g., Fruits and vegetables, Common restaurant phrases, Daily routines"
                        disabled={isSubmitting}
                    />
                </div>

                <div className="flex flex-col gap-2">
                    <Label htmlFor="cardCount">Number of cards</Label>
                    <select
                        id="cardCount"
                        name="cardCount"
                        value={cardCount}
                        onChange={(event) => setCardCount(parseInt(event.target.value))}
                        className="w-full rounded-md border border-slate-200 bg-white p-3 text-sm shadow-sm focus:border-slate-400 focus:outline-none focus:ring-2 focus:ring-slate-200"
                        disabled={isSubmitting}
                    >
                        <option value={5}>5 cards</option>
                        <option value={10}>10 cards</option>
                        <option value={15}>15 cards</option>
                        <option value={20}>20 cards</option>
                    </select>
                </div>

                {error ? (
                    <p className="text-sm text-red-600" role="alert">
                        {error}
                    </p>
                ) : null}

                {isSubmitting && (
                    <div className="rounded-lg bg-blue-50 p-4 border border-blue-200">
                        <p className="text-sm text-blue-800">
                            Creating flash card deck with <span className="font-semibold">Fast Model (GPT-4o Mini)</span>...
                        </p>
                        <p className="text-xs text-blue-600 mt-1">
                            Generating {cardCount} flash cards for you.
                        </p>
                        <div className="mt-3 pt-3 border-t border-blue-200">
                            <p className="text-sm text-blue-800">
                                Time elapsed: <span className="font-semibold">{elapsedSeconds}s</span>
                            </p>
                            <p className="text-xs text-blue-600 mt-1">
                                Average generation time: ~15-30 seconds
                            </p>
                        </div>
                    </div>
                )}

                <div className="flex items-center justify-end gap-4">
                    <Button
                        type="button"
                        variant="outline"
                        onClick={() => router.push("/flash-cards")}
                        disabled={isSubmitting}
                    >
                        Cancel
                    </Button>
                    <Button type="submit" disabled={isSubmitting}>
                        {isSubmitting ? "Creating deck..." : "Create deck"}
                    </Button>
                </div>
            </form>
        </section>
    );
}
