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
    const [modelType, setModelType] = useState<'fast' | 'detailed'>('detailed');
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [elapsedSeconds, setElapsedSeconds] = useState(0);
    const [userLanguages, setUserLanguages] = useState<{
        baseLanguage: string;
        targetLanguage: string;
    } | null>(null);

    // Fetch user language settings
    useEffect(() => {
        const fetchUserLanguages = async () => {
            try {
                const response = await fetch('/api/user/me');
                if (response.ok) {
                    const userData = await response.json();
                    setUserLanguages({
                        baseLanguage: userData.baseLanguage || 'English',
                        targetLanguage: userData.targetLanguage || 'German',
                    });
                }
            } catch (err) {
                console.error('Failed to fetch user languages:', err);
            }
        };
        fetchUserLanguages();
    }, []);

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

    const capitalizeLanguage = (lang: string) => {
        return lang.charAt(0).toUpperCase() + lang.slice(1).toLowerCase();
    };

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
                modelType,
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
                {userLanguages && (
                    <div className="rounded-lg bg-slate-50 p-4 border border-slate-200">
                        <h3 className="font-semibold text-sm mb-2">Language Settings</h3>
                        <div className="flex gap-6 text-sm">
                            <div>
                                <span className="text-slate-600">Base Language:</span>{' '}
                                <span className="font-medium">{capitalizeLanguage(userLanguages.baseLanguage)}</span>
                            </div>
                            <div>
                                <span className="text-slate-600">Target Language:</span>{' '}
                                <span className="font-medium">{capitalizeLanguage(userLanguages.targetLanguage)}</span>
                            </div>
                        </div>
                    </div>
                )}

                <div className="flex flex-col gap-2">
                    <Label htmlFor="topic">Lesson topic</Label>
                    <textarea
                        id="topic"
                        name="topic"
                        value={topic}
                        onChange={(event) => setTopic(event.target.value)}
                        className="min-h-48 w-full rounded-md border border-slate-200 bg-white p-3 text-sm shadow-sm focus:border-slate-400 focus:outline-none focus:ring-2 focus:ring-slate-200"
                        placeholder="Describe what you want to learn... e.g., Say hello; Explain the Dative Case"
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

                <div className="flex flex-col gap-3">
                    <Label>Model Selection</Label>
                    <div className="flex flex-col gap-2">
                        <label className={`flex items-start gap-3 rounded-lg border p-4 cursor-pointer transition-colors ${
                            modelType === 'detailed'
                                ? 'border-blue-500 bg-blue-50'
                                : 'border-slate-200 bg-white hover:border-slate-300'
                        }`}>
                            <input
                                type="radio"
                                name="modelType"
                                value="detailed"
                                checked={modelType === 'detailed'}
                                onChange={(e) => setModelType(e.target.value as 'detailed')}
                                disabled={isSubmitting}
                                className="mt-0.5"
                            />
                            <div className="flex-1">
                                <div className="font-semibold text-sm">Detailed Model (GPT-5 Nano)</div>
                                <div className="text-xs text-slate-600 mt-1">
                                    More thorough and comprehensive responses. Best for complex topics.
                                </div>
                                <div className="text-xs text-slate-500 mt-1">
                                    Cost: $0.05/1M input tokens, $0.40/1M output tokens
                                </div>
                            </div>
                        </label>

                        <label className={`flex items-start gap-3 rounded-lg border p-4 cursor-pointer transition-colors ${
                            modelType === 'fast'
                                ? 'border-blue-500 bg-blue-50'
                                : 'border-slate-200 bg-white hover:border-slate-300'
                        }`}>
                            <input
                                type="radio"
                                name="modelType"
                                value="fast"
                                checked={modelType === 'fast'}
                                onChange={(e) => setModelType(e.target.value as 'fast')}
                                disabled={isSubmitting}
                                className="mt-0.5"
                            />
                            <div className="flex-1">
                                <div className="font-semibold text-sm">Fast Model (GPT-4o Mini)</div>
                                <div className="text-xs text-slate-600 mt-1">
                                    Quick and efficient responses. Good for simple topics and faster generation.
                                </div>
                                <div className="text-xs text-slate-500 mt-1">
                                    Cost: $0.15/1M input tokens, $0.60/1M output tokens
                                </div>
                            </div>
                        </label>
                    </div>
                </div>

                {error ? (
                    <p className="text-sm text-red-600" role="alert">
                        {error}
                    </p>
                ) : null}

                {isSubmitting && (
                    <div className="rounded-lg bg-blue-50 p-4 border border-blue-200">
                        <p className="text-sm text-blue-800">
                            Creating lesson with <span className="font-semibold">
                                {modelType === 'detailed' ? 'Detailed Model (GPT-5 Nano)' : 'Fast Model (GPT-4o Mini)'}
                            </span>...
                        </p>
                        <p className="text-xs text-blue-600 mt-1">
                            {modelType === 'detailed'
                                ? 'This may take a moment as we generate comprehensive content for you.'
                                : 'Generating your lesson quickly...'}
                        </p>
                        <div className="mt-3 pt-3 border-t border-blue-200">
                            <p className="text-sm text-blue-800">
                                Time elapsed: <span className="font-semibold">{elapsedSeconds}s</span>
                            </p>
                            <p className="text-xs text-blue-600 mt-1">
                                Average generation time: ~{modelType === 'detailed' ? '1 minute' : '30 seconds'}
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
