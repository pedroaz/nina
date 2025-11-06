"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { DualLanguageTextCard, type DualLanguageContent } from "@/components/dual-language-text-card";
import { Loader2 } from "lucide-react";

interface ExtraSectionsInputProps {
    lessonId: string;
    initialExtraSections?: DualLanguageContent[];
}

export function ExtraSectionsInput({ lessonId, initialExtraSections = [] }: ExtraSectionsInputProps) {
    const [request, setRequest] = useState("");
    const [extraSections, setExtraSections] = useState<DualLanguageContent[]>(initialExtraSections);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!request.trim()) return;

        setIsLoading(true);
        setError(null);

        try {
            const response = await fetch(`/api/lessons/${lessonId}/extra-sections`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({ request }),
            });

            if (!response.ok) {
                throw new Error("Failed to generate extra section");
            }

            const updatedLesson = await response.json();

            // Update the extra sections with the full array from the response
            if (updatedLesson.extraSections) {
                setExtraSections(updatedLesson.extraSections);
            }

            setRequest("");
        } catch (err) {
            setError(err instanceof Error ? err.message : "An error occurred");
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="space-y-8">
            {extraSections.length > 0 && (
                <div className="space-y-8">
                    {extraSections.map((section, index) => (
                        <DualLanguageTextCard
                            key={index}
                            heading={`Extra Section ${index + 1}`}
                            content={section}
                            emptyMessage="No content available."
                        />
                    ))}
                </div>
            )}

            <div className="rounded-lg border border-slate-200 bg-slate-50 p-6">
                <h3 className="mb-4 text-lg font-medium">Request Additional Content</h3>
                <form onSubmit={handleSubmit} className="space-y-4">
                    <Input
                        type="text"
                        placeholder="Give me 5 more examples or explain this in a different way"
                        value={request}
                        onChange={(e) => setRequest(e.target.value)}
                        disabled={isLoading}
                        className="w-full"
                    />
                    <div className="flex items-center gap-4">
                        <Button type="submit" disabled={isLoading || !request.trim()}>
                            {isLoading ? (
                                <>
                                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                    Generating...
                                </>
                            ) : (
                                "Generate"
                            )}
                        </Button>
                        {error && <p className="text-sm text-red-500">{error}</p>}
                    </div>
                </form>
            </div>
        </div>
    );
}
