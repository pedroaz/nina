'use client';

import { FormEvent, useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { CreateLessonRequestData } from "@core/cqrs/lesson-commands";

export default function CustomLessonsNew() {
    const router = useRouter();
    const [topic, setTopic] = useState("");
    const [vocabulary, setVocabulary] = useState("");
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
        const sanitizedVocabulary = vocabulary.trim();

        if (!sanitizedTopic) {
            setError("Please provide a topic for your lesson request.");
            return;
        }

        setIsSubmitting(true);
        setError(null);

        try {
            const requestBody: CreateLessonRequestData = {
                topic: sanitizedTopic,
                vocabulary: sanitizedVocabulary,
            };
            const response = await fetch("/api/lessons", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(requestBody),
            });

            if (response.status === 401) {
                router.push(
                    `/api/auth/signin?callbackUrl=${encodeURIComponent("/lessons/new")}`,
                );
                return;
            }

            if (!response.ok) {
                const payload = await response.json().catch(() => null);
                const message =
                    typeof payload?.error === "string"
                        ? payload.error
                        : "Unable to submit your lesson request.";
                throw new Error(message);
            }

            setTopic("");
            setVocabulary("");
            router.push("/lessons");
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
                    <Label htmlFor="topic">Lesson topic</Label>
                    <textarea
                        id="topic"
                        name="topic"
                        value={topic}
                        onChange={(event) => setTopic(event.target.value)}
                        className="min-h-48 w-full rounded-md border border-slate-200 bg-white p-3 text-sm shadow-sm focus:border-slate-400 focus:outline-none focus:ring-2 focus:ring-slate-200"
                        placeholder="Describe what you want to learn... e.g., Say hello in German; Explain the Dative Case"
                        disabled={isSubmitting}
                    />
                </div>

                <div className="flex flex-col gap-2">
                    <Label htmlFor="vocabulary">Vocabulary focus</Label>
                    <textarea
                        id="vocabulary"
                        name="vocabulary"
                        value={vocabulary}
                        onChange={(event) => setVocabulary(event.target.value)}
                        className="min-h-24 w-full rounded-md border border-slate-200 bg-white p-3 text-sm shadow-sm focus:border-slate-400 focus:outline-none focus:ring-2 focus:ring-slate-200"
                        placeholder="Animals, Furniture"
                        disabled={isSubmitting}
                    />
                </div>

                {error ? (
                    <p className="text-sm text-red-600" role="alert">
                        {error}
                    </p>
                ) : null}

                {isSubmitting && (
                    <div className="rounded-lg bg-blue-50 p-4 border border-blue-200">
                        <p className="text-sm text-blue-800">
                            Creating lesson with <span className="font-semibold">Detailed Model (GPT-5 Nano)</span>...
                        </p>
                        <p className="text-xs text-blue-600 mt-1">
                            This may take a moment as we generate comprehensive content for you.
                        </p>
                        <div className="mt-3 pt-3 border-t border-blue-200">
                            <p className="text-sm text-blue-800">
                                Time elapsed: <span className="font-semibold">{elapsedSeconds}s</span>
                            </p>
                            <p className="text-xs text-blue-600 mt-1">
                                Average generation time: ~1 minute
                            </p>
                        </div>
                    </div>
                )}

                <div className="flex items-center justify-end gap-4">
                    <Button
                        type="button"
                        variant="outline"
                        onClick={() => router.push("/lessons")}
                        disabled={isSubmitting}
                    >
                        Cancel
                    </Button>
                    <Button type="submit" disabled={isSubmitting}>
                        {isSubmitting ? "Creating lesson..." : "Submit request"}
                    </Button>
                </div>
            </form>
        </section>
    );
}
