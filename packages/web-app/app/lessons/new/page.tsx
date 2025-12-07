'use client';

import { FormEvent, useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { FlashCardMiniGame } from "@/components/flashcard-mini-game";
import { BookText, GraduationCap, Image as ImageIcon, Sparkles, Zap } from "lucide-react";

export default function CustomLessonsNew() {
    const router = useRouter();
    const [topic, setTopic] = useState("");
    const [image, setImage] = useState<string | null>(null);
    const [modelType, setModelType] = useState<'fast' | 'detailed'>('detailed');
    const [focus, setFocus] = useState<'vocabulary' | 'grammar' | null>(null);
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

    const handleImageUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (file) {
            const reader = new FileReader();
            reader.onloadend = () => {
                setImage(reader.result as string);
            };
            reader.readAsDataURL(file);
        }
    };

    const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
        event.preventDefault();

        const sanitizedTopic = topic.trim();

        if (!sanitizedTopic) {
            setError("Please provide a topic for your lesson request.");
            return;
        }

        setIsSubmitting(true);
        setError(null);

        try {
            const requestBody = {
                topic: sanitizedTopic,
                vocabulary: "", // No longer separate
                modelType,
                focus: focus || undefined,
                image: image || undefined,
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
                className="flex w-full max-w-2xl flex-col gap-6 rounded-xl border border-neutral-200 bg-white p-8 shadow-sm"
            >
                {userLanguages && (
                    <div className="rounded-lg bg-neutral-50 p-4 border border-neutral-200">
                        <h3 className="font-semibold text-sm mb-2">Language Settings</h3>
                        <div className="flex gap-6 text-sm">
                            <div>
                                <span className="text-neutral-600">Base Language:</span>{' '}
                                <span className="font-medium">{capitalizeLanguage(userLanguages.baseLanguage)}</span>
                            </div>
                            <div>
                                <span className="text-neutral-600">Target Language:</span>{' '}
                                <span className="font-medium">{capitalizeLanguage(userLanguages.targetLanguage)}</span>
                            </div>
                        </div>
                    </div>
                )}

                <div className="flex flex-col gap-2">
                    <Label htmlFor="topic">What do you want to learn?</Label>
                    <textarea
                        id="topic"
                        name="topic"
                        value={topic}
                        onChange={(event) => setTopic(event.target.value)}
                        className="min-h-32 w-full rounded-md border border-neutral-200 bg-white p-3 text-sm shadow-sm focus:border-neutral-300 focus:outline-none focus:ring-2 focus:ring-neutral-200"
                        placeholder="e.g., How to order food at a restaurant&#10;&#10;💡 Tip: You can focus on specific vocabulary by mentioning it (e.g., 'restaurant vocabulary')"
                        disabled={isSubmitting}
                    />
                </div>

                <div className="flex flex-wrap gap-3">
                    <button
                        type="button"
                        onClick={() => setFocus(focus === 'vocabulary' ? null : 'vocabulary')}
                        className={`flex items-center gap-2 px-4 py-2 rounded-lg border transition-all ${focus === 'vocabulary'
                                ? 'border-orange-500 bg-orange-50 text-orange-700'
                                : 'border-neutral-200 bg-white hover:border-neutral-300'
                            }`}
                        disabled={isSubmitting}
                    >
                        <BookText className="h-4 w-4" />
                        <span className="text-sm font-medium">Vocabulary Focus</span>
                    </button>

                    <button
                        type="button"
                        onClick={() => setFocus(focus === 'grammar' ? null : 'grammar')}
                        className={`flex items-center gap-2 px-4 py-2 rounded-lg border transition-all ${focus === 'grammar'
                                ? 'border-orange-500 bg-orange-50 text-orange-700'
                                : 'border-neutral-200 bg-white hover:border-neutral-300'
                            }`}
                        disabled={isSubmitting}
                    >
                        <GraduationCap className="h-4 w-4" />
                        <span className="text-sm font-medium">Grammar Focus</span>
                    </button>

                    <label className={`flex items-center gap-2 px-4 py-2 rounded-lg border cursor-pointer transition-all ${image
                            ? 'border-orange-500 bg-orange-50 text-orange-700'
                            : 'border-neutral-200 bg-white hover:border-neutral-300'
                        }`}>
                        <ImageIcon className="h-4 w-4" />
                        <span className="text-sm font-medium">
                            {image ? 'Image Added' : 'Add Image'}
                        </span>
                        <input
                            type="file"
                            accept="image/*"
                            onChange={handleImageUpload}
                            className="hidden"
                            disabled={isSubmitting}
                        />
                    </label>

                    {image && (
                        <button
                            type="button"
                            onClick={() => setImage(null)}
                            className="flex items-center gap-2 px-4 py-2 rounded-lg border border-error-border bg-error-bg text-error-text hover:bg-error-bg transition-all"
                        >
                            <span className="text-sm font-medium">Remove Image</span>
                        </button>
                    )}
                </div>

                {image && (
                    <div className="relative w-full h-48 rounded-lg overflow-hidden border border-neutral-200">
                        <img src={image} alt="Preview" className="object-cover w-full h-full" />
                    </div>
                )}

                <div className="flex gap-3">
                    <button
                        type="button"
                        onClick={() => setModelType('detailed')}
                        className={`flex-1 flex items-center justify-center gap-2 px-4 py-3 rounded-lg border transition-all ${modelType === 'detailed'
                                ? 'border-orange-500 bg-orange-50 text-orange-700'
                                : 'border-neutral-200 bg-white hover:border-neutral-300'
                            }`}
                        disabled={isSubmitting}
                    >
                        <Sparkles className="h-4 w-4" />
                        <div className="text-left">
                            <div className="text-sm font-semibold">Detailed</div>
                            <div className="text-xs opacity-75">Comprehensive</div>
                        </div>
                    </button>

                    <button
                        type="button"
                        onClick={() => setModelType('fast')}
                        className={`flex-1 flex items-center justify-center gap-2 px-4 py-3 rounded-lg border transition-all ${modelType === 'fast'
                                ? 'border-orange-500 bg-orange-50 text-orange-700'
                                : 'border-neutral-200 bg-white hover:border-neutral-300'
                            }`}
                        disabled={isSubmitting}
                    >
                        <Zap className="h-4 w-4" />
                        <div className="text-left">
                            <div className="text-sm font-semibold">Fast</div>
                            <div className="text-xs opacity-75">Quick & Efficient</div>
                        </div>
                    </button>
                </div>

                {error ? (
                    <p className="text-sm text-error-text" role="alert">
                        {error}
                    </p>
                ) : null}

                {isSubmitting && (
                    <div className="rounded-lg bg-teal-50 p-4 border border-teal-200">
                        <p className="text-sm text-teal-900">
                            Creating lesson with <span className="font-semibold">
                                {modelType === 'detailed' ? 'Detailed Model' : 'Fast Model'}
                            </span>...
                        </p>
                        <p className="text-xs text-teal-600 mt-1">
                            Time elapsed: <span className="font-semibold">{elapsedSeconds}s</span>
                        </p>
                        <div className="mt-4 pt-4 border-t border-teal-200">
                            <p className="text-sm text-teal-900 mb-3">
                                Practice flashcards while you wait:
                            </p>
                            <FlashCardMiniGame className="bg-white rounded-lg p-4" />
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
                        {isSubmitting ? "Creating lesson..." : "Create Lesson"}
                    </Button>
                </div>
            </form>
        </section>
    );
}
