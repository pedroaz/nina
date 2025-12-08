'use client';

import { useState, FormEvent, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { PentagonSpinner } from "@/components/pentagon-spinner";

export default function NewMissionPage() {
    const router = useRouter();
    const [topic, setTopic] = useState("");
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
            setError("Please provide a topic for your mission.");
            return;
        }

        setIsSubmitting(true);
        setError(null);

        try {
            const response = await fetch("/api/missions", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ topic: sanitizedTopic }),
            });

            if (response.status === 401) {
                router.push(
                    `/api/auth/signin?callbackUrl=${encodeURIComponent("/missions/new")}`,
                );
                return;
            }

            if (!response.ok) {
                const payload = await response.json().catch(() => null);
                const message =
                    typeof payload?.error === "string"
                        ? payload.error
                        : "Unable to create mission.";
                throw new Error(message);
            }

            setTopic("");
            router.push("/missions");
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
                    <Label htmlFor="topic" className="text-lg font-bold">What scenario do you want to practice?</Label>
                    <p className="text-sm text-neutral-500">
                        Describe a situation you want to roleplay.
                    </p>
                    <textarea
                        id="topic"
                        name="topic"
                        value={topic}
                        onChange={(event) => setTopic(event.target.value)}
                        className="min-h-32 w-full rounded-md border border-neutral-200 bg-white p-3 text-sm shadow-sm focus:border-neutral-300 focus:outline-none focus:ring-2 focus:ring-neutral-200"
                        placeholder="e.g., Buying a train ticket in Berlin. Tip: Be specific about the location or context."
                        disabled={isSubmitting}
                    />
                </div>

                {error ? (
                    <div className="rounded-md bg-red-50 p-3 text-sm text-red-600">
                        {error}
                    </div>
                ) : null}

                {isSubmitting && (
                    <div className="rounded-md bg-blue-50 border border-blue-200 p-6">
                        <div className="flex items-center justify-center gap-4">
                            <div className="flex flex-col gap-1">
                                <span className="font-semibold text-neutral-900">Creating your mission...</span>
                                <span className="text-sm text-neutral-600">
                                    This usually takes about 10-20 seconds. ({elapsedSeconds}s elapsed)
                                </span>
                            </div>
                        </div>
                    </div>
                )}

                <div className="flex items-center justify-end gap-4">
                    <Button
                        type="button"
                        variant="ghost"
                        onClick={() => router.back()}
                        disabled={isSubmitting}
                    >
                        Cancel
                    </Button>
                    <Button type="submit" disabled={isSubmitting || !topic.trim()}>
                        {isSubmitting ? "Creating..." : "Create Mission"}
                    </Button>
                </div>
            </form>
        </section>
    );
}
