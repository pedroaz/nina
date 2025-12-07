'use client';

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
    DialogTrigger,
} from "@/components/ui/dialog";

interface GenerateExercisesDialogProps {
    lessonId: string;
    lessonTitle: string;
}

export function GenerateExercisesDialog({ lessonId, lessonTitle }: GenerateExercisesDialogProps) {
    const router = useRouter();
    const [open, setOpen] = useState(false);
    const [setTitle, setSetTitle] = useState(lessonTitle);
    const [exerciseType, setExerciseType] = useState<'multiple_choice' | 'sentence_creation'>('multiple_choice');
    const [exerciseCount, setExerciseCount] = useState(10);
    const [isGenerating, setIsGenerating] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const handleGenerate = async () => {
        if (!setTitle.trim()) {
            setError("Please provide a set title.");
            return;
        }

        setIsGenerating(true);
        setError(null);

        try {
            const response = await fetch("/api/exercise-sets", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    source: 'from-lesson',
                    exerciseType,
                    lessonId,
                    setTitle: setTitle.trim(),
                    exerciseCount,
                }),
            });

            if (!response.ok) {
                const payload = await response.json().catch(() => null);
                const message =
                    typeof payload?.error === "string"
                        ? payload.error
                        : "Failed to generate exercises.";
                throw new Error(message);
            }

            const exerciseSet = await response.json();

            // Close dialog and redirect to new exercise set
            setOpen(false);
            router.push(`/exercises/${exerciseSet._id}`);
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
                <Button variant="outline">Generate Exercises</Button>
            </DialogTrigger>
            <DialogContent className="sm:max-w-[500px]">
                <DialogHeader>
                    <DialogTitle>Generate Exercises from Lesson</DialogTitle>
                    <DialogDescription>
                        Create a set of exercises based on this lesson&apos;s content.
                    </DialogDescription>
                </DialogHeader>
                <div className="grid gap-4 py-4">
                    <div className="grid gap-2">
                        <Label htmlFor="setTitle">Exercise set title</Label>
                        <Input
                            id="setTitle"
                            value={setTitle}
                            onChange={(e) => setSetTitle(e.target.value)}
                            disabled={isGenerating}
                        />
                    </div>
                    <div className="grid gap-3">
                        <Label>Exercise type</Label>
                        <RadioGroup
                            value={exerciseType}
                            onValueChange={(value) => setExerciseType(value as 'multiple_choice' | 'sentence_creation')}
                            disabled={isGenerating}
                        >
                            <div className="flex items-center space-x-2 rounded-lg border border-neutral-200 p-3 hover:bg-neutral-50">
                                <RadioGroupItem value="multiple_choice" id="mc" />
                                <Label htmlFor="mc" className="flex-1 cursor-pointer">
                                    <div className="font-medium text-sm">Multiple Choice</div>
                                    <div className="text-xs text-neutral-600">Choose from 4 options</div>
                                </Label>
                            </div>
                            <div className="flex items-center space-x-2 rounded-lg border border-neutral-200 p-3 hover:bg-neutral-50">
                                <RadioGroupItem value="sentence_creation" id="sc" />
                                <Label htmlFor="sc" className="flex-1 cursor-pointer">
                                    <div className="font-medium text-sm">Sentence Creation</div>
                                    <div className="text-xs text-neutral-600">Write sentences, judged by AI</div>
                                </Label>
                            </div>
                        </RadioGroup>
                    </div>
                    <div className="grid gap-2">
                        <Label htmlFor="exerciseCount">Number of exercises</Label>
                        <select
                            id="exerciseCount"
                            value={exerciseCount}
                            onChange={(e) => setExerciseCount(parseInt(e.target.value))}
                            className="w-full rounded-md border border-neutral-200 bg-white p-2 text-sm shadow-sm focus:border-neutral-300 focus:outline-none focus:ring-2 focus:ring-neutral-200"
                            disabled={isGenerating}
                        >
                            <option value={5}>5 exercises</option>
                            <option value={10}>10 exercises</option>
                            <option value={15}>15 exercises</option>
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
                                Generating {exerciseType === 'multiple_choice' ? 'multiple choice' : 'sentence creation'} exercises...
                            </p>
                        </div>
                    )}
                </div>
                <DialogFooter>
                    <Button
                        type="button"
                        variant="outline"
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
