'use client';

import { FormEvent, useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";

export default function NewExerciseSet() {
    const router = useRouter();
    const [topic, setTopic] = useState("");
    const [exerciseType, setExerciseType] = useState<'multiple_choice' | 'sentence_creation'>('multiple_choice');
    const [exerciseCount, setExerciseCount] = useState(10);
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
            setError("Please provide a topic for your exercise set.");
            return;
        }

        setIsSubmitting(true);
        setError(null);

        try {
            const requestBody = {
                source: 'from-prompt',
                exerciseType: exerciseType,
                topic: sanitizedTopic,
                exerciseCount: exerciseCount,
            };

            const response = await fetch("/api/exercise-sets", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(requestBody),
            });

            if (response.status === 401) {
                router.push(
                    `/api/auth/signin?callbackUrl=${encodeURIComponent("/exercises/new")}`,
                );
                return;
            }

            if (!response.ok) {
                const payload = await response.json().catch(() => null);
                const message =
                    typeof payload?.error === "string"
                        ? payload.error
                        : "Unable to create your exercise set.";
                throw new Error(message);
            }

            const exerciseSet = await response.json();

            setTopic("");
            setExerciseCount(10);
            router.push(`/exercises/${exerciseSet._id}`);
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
                className="flex w-full max-w-2xl flex-col gap-6 rounded-xl border border-neutral-200 bg-white p-8 shadow-sm"
            >
                <div className="flex flex-col gap-2">
                    <h1 className="text-2xl font-semibold">Create Exercise Set</h1>
                    <p className="text-sm text-neutral-600">
                        Generate interactive exercises on any topic to practice your language skills.
                    </p>
                </div>

                <div className="flex flex-col gap-3">
                    <Label>Exercise type</Label>
                    <RadioGroup
                        value={exerciseType}
                        onValueChange={(value) => setExerciseType(value as 'multiple_choice' | 'sentence_creation')}
                        disabled={isSubmitting}
                    >
                        <div className="flex items-center space-x-2 rounded-lg border border-neutral-200 p-4 hover:bg-neutral-50">
                            <RadioGroupItem value="multiple_choice" id="multiple_choice" />
                            <Label htmlFor="multiple_choice" className="flex-1 cursor-pointer">
                                <div className="font-medium">Multiple Choice</div>
                                <div className="text-xs text-neutral-600">Answer questions by choosing from 4 options</div>
                            </Label>
                        </div>
                        <div className="flex items-center space-x-2 rounded-lg border border-neutral-200 p-4 hover:bg-neutral-50">
                            <RadioGroupItem value="sentence_creation" id="sentence_creation" />
                            <Label htmlFor="sentence_creation" className="flex-1 cursor-pointer">
                                <div className="font-medium">Sentence Creation</div>
                                <div className="text-xs text-neutral-600">Write sentences based on prompts, judged by AI</div>
                            </Label>
                        </div>
                    </RadioGroup>
                </div>

                <div className="flex flex-col gap-2">
                    <Label htmlFor="topic">Exercise topic</Label>
                    <textarea
                        id="topic"
                        name="topic"
                        value={topic}
                        onChange={(event) => setTopic(event.target.value)}
                        className="min-h-32 w-full rounded-md border border-neutral-200 bg-white p-3 text-sm shadow-sm focus:border-neutral-300 focus:outline-none focus:ring-2 focus:ring-neutral-200"
                        placeholder="e.g., Past tense verbs, Asking for directions, Ordering food at a restaurant"
                        disabled={isSubmitting}
                    />
                </div>

                <div className="flex flex-col gap-2">
                    <Label htmlFor="exerciseCount">Number of exercises</Label>
                    <select
                        id="exerciseCount"
                        name="exerciseCount"
                        value={exerciseCount}
                        onChange={(event) => setExerciseCount(parseInt(event.target.value))}
                        className="w-full rounded-md border border-neutral-200 bg-white p-3 text-sm shadow-sm focus:border-neutral-300 focus:outline-none focus:ring-2 focus:ring-neutral-200"
                        disabled={isSubmitting}
                    >
                        <option value={5}>5 exercises</option>
                        <option value={10}>10 exercises</option>
                        <option value={15}>15 exercises</option>
                    </select>
                </div>

                {error ? (
                    <p className="text-sm text-error-text" role="alert">
                        {error}
                    </p>
                ) : null}

                {isSubmitting && (
                    <div className="rounded-lg bg-teal-50 p-4 border border-teal-200">
                        <p className="text-sm text-teal-900">
                            Creating {exerciseType === 'multiple_choice' ? 'multiple choice' : 'sentence creation'} exercises with <span className="font-semibold">Fast Model (GPT-4o Mini)</span>...
                        </p>
                        <p className="text-xs text-teal-600 mt-1">
                            Generating {exerciseCount} exercises for you.
                        </p>
                        <div className="mt-3 pt-3 border-t border-teal-200">
                            <p className="text-sm text-teal-900">
                                Time elapsed: <span className="font-semibold">{elapsedSeconds}s</span>
                            </p>
                            <p className="text-xs text-teal-600 mt-1">
                                Average generation time: ~15-30 seconds
                            </p>
                        </div>
                    </div>
                )}

                <div className="flex items-center justify-end gap-4">
                    <Button
                        type="button"
                        variant="destructive"
                        onClick={() => router.push("/exercises")}
                        disabled={isSubmitting}
                    >
                        Cancel
                    </Button>
                    <Button type="submit" disabled={isSubmitting}>
                        {isSubmitting ? "Creating exercises..." : "Create exercises"}
                    </Button>
                </div>
            </form>
        </section>
    );
}
