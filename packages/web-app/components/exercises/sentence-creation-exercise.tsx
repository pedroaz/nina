'use client';

import React from 'react';
import { Button } from "@/components/ui/button";
import logger from "@/lib/logger";

type DualLanguage = {
    base: string;
    target: string;
};

type SentenceCreationExercise = {
    _id: string;
    prompt: DualLanguage;
    referenceAnswer: string;
    context?: string;
};

type SubmissionResult = {
    isCorrect?: boolean;
    score?: number;
    feedback?: string;
};

interface SentenceCreationExerciseProps {
    exercise: SentenceCreationExercise;
    setId: string;
    showTranslation: boolean;
    onTranslationToggle: (show: boolean) => void;
    onSubmit: (result: SubmissionResult) => void;
    result: SubmissionResult | null;
    submitting: boolean;
}

export function SentenceCreationExerciseComponent({
    exercise,
    setId,
    showTranslation,
    onTranslationToggle,
    onSubmit,
    result,
    submitting,
}: SentenceCreationExerciseProps) {
    const [userSentence, setUserSentence] = React.useState("");

    const handleSubmit = async () => {
        if (!userSentence.trim()) return;

        logger.info(`Submitting exercise: ${exercise._id}`);

        try {
            const response = await fetch(`/api/exercise-sets/${setId}/submit`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    exerciseId: exercise._id,
                    userAnswer: userSentence,
                }),
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                console.error('Submit error:', errorData);
                throw new Error(errorData.error || 'Failed to submit answer');
            }

            const submissionResult = await response.json();
            onSubmit(submissionResult);
        } catch (error) {
            console.error('Error submitting answer:', error);
            alert(`Error: ${error instanceof Error ? error.message : 'Failed to submit answer'}`);
        }
    };

    if (result) {
        return (
            <div className="space-y-4">
                {/* User's Answer */}
                <div className="rounded-lg border border-neutral-200 bg-neutral-50 p-4">
                    <p className="text-sm font-medium text-neutral-700 mb-2">Your answer:</p>
                    <p className="text-base">{userSentence}</p>
                </div>

                {/* Score and Feedback */}
                <div className={`rounded-lg border p-4 ${(result.score || 0) >= 80 ? 'border-green-600 bg-green-50' :
                    (result.score || 0) >= 60 ? 'border-yellow-200 bg-yellow-50' :
                        'border-red-600 bg-red-50'
                    }`}>
                    <div className="flex items-center justify-between mb-2">
                        <span className="text-sm font-medium">Score</span>
                        <span className="text-2xl font-bold">{result.score}/100</span>
                    </div>
                    <p className="text-sm mt-3">{result.feedback}</p>
                </div>

                {/* Reference Answer */}
                <div className="rounded-lg border border-teal-200 bg-teal-50 p-4">
                    <p className="text-sm font-medium text-teal-900 mb-2">Reference answer:</p>
                    <p className="text-sm text-teal-700">{exercise.referenceAnswer}</p>
                </div>
            </div>
        );
    }

    return (
        <div className="space-y-6">
            {/* Prompt */}
            <div className="space-y-2">
                <div className="flex justify-between items-start">
                    <h3 className="text-lg font-medium">Prompt</h3>
                    <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => onTranslationToggle(!showTranslation)}
                    >
                        Show Translation
                    </Button>
                </div>
                <p className="text-lg font-medium">{exercise.prompt.target}</p>
                {showTranslation && (
                    <p className="text-sm text-neutral-600">{exercise.prompt.base}</p>
                )}
                {exercise.context && (
                    <p className="text-sm italic text-neutral-500">{exercise.context}</p>
                )}
            </div>

            {/* Input */}
            <textarea
                value={userSentence}
                onChange={(e) => setUserSentence(e.target.value)}
                className="min-h-32 w-full rounded-md border border-neutral-200 bg-white p-3 text-sm shadow-sm focus:border-neutral-300 focus:outline-none focus:ring-2 focus:ring-neutral-200"
                placeholder="Write your sentence here..."
                disabled={submitting}
            />

            {/* Submit Button */}
            <Button
                onClick={handleSubmit}
                disabled={!userSentence.trim() || submitting}
                className="w-full"
            >
                {submitting ? 'Judging your answer...' : 'Submit answer'}
            </Button>
        </div>
    );
}
