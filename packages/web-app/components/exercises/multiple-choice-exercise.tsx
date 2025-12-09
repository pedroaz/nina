'use client';

import React from 'react';
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import logger from "@/lib/logger";

type DualLanguage = {
    base: string;
    target: string;
};

type MultipleChoiceExercise = {
    _id: string;
    question: DualLanguage;
    options: DualLanguage[];
    correctOptionIndex: number;
};

type SubmissionResult = {
    isCorrect?: boolean;
    score?: number;
    feedback?: string;
};

interface MultipleChoiceExerciseProps {
    exercise: MultipleChoiceExercise;
    setId: string;
    showTranslation: boolean;
    onTranslationToggle: (show: boolean) => void;
    onSubmit: (result: SubmissionResult) => void;
    submitted: boolean;
    result: SubmissionResult | null;
}

export function MultipleChoiceExerciseComponent({
    exercise,
    setId,
    showTranslation,
    onTranslationToggle,
    onSubmit,
    submitted,
    result,
}: MultipleChoiceExerciseProps) {
    const [selectedOption, setSelectedOption] = React.useState<number | null>(null);

    React.useEffect(() => {
        // Reset selected option when the exercise changes
        setSelectedOption(null);
    }, [exercise]);

    const handleSubmit = async () => {
        if (selectedOption === null) return;

        logger.info(`Submitting exercise: ${exercise._id}`);

        try {
            const response = await fetch(`/api/exercise-sets/${setId}/submit`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    exerciseId: exercise._id,
                    userAnswer: String(selectedOption),
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

    return (
        <div className="space-y-6">
            {/* Question */}
            <div className="space-y-2">
                <div className="flex justify-between items-start">
                    <h3 className="text-lg font-medium">Question</h3>
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={() => onTranslationToggle(!showTranslation)}
                    >
                        Show Translation
                    </Button>
                </div>
                <p className="text-lg font-medium">{exercise.question.target}</p>
                {showTranslation && (
                    <p className="text-sm text-neutral-600">{exercise.question.base}</p>
                )}
            </div>

            {/* Options */}
            <div className="space-y-2">
                {exercise.options.map((option, index) => {
                    const isSelected = selectedOption === index;
                    const isCorrect = index === exercise.correctOptionIndex;
                    const showResult = submitted;

                    let buttonClass = "w-full justify-start text-left h-auto p-4 ";
                    if (showResult) {
                        if (isCorrect) {
                            buttonClass += "border-green-600 bg-green-50 hover:bg-green-50";
                        } else if (isSelected && !isCorrect) {
                            buttonClass += "border-red-600 bg-red-50 hover:bg-red-50";
                        }
                    } else if (isSelected) {
                        buttonClass += "border-orange-500 bg-orange-50";
                    }

                    return (
                        <Button
                            key={index}
                            className={buttonClass}
                            onClick={() => {
                                if (!submitted) {
                                    setSelectedOption(index);
                                }
                            }}
                            disabled={submitted}
                            variant="outline"
                        >
                            <div className="space-y-1 w-full">
                                <div className="font-medium">{option.target}</div>
                                {showTranslation && (
                                    <div className="text-sm text-neutral-600">{option.base}</div>
                                )}
                                {showResult && isCorrect && (
                                    <Badge className="mt-2" variant="default">Correct</Badge>
                                )}
                            </div>
                        </Button>
                    );
                })}
            </div>

            {/* Submit Button */}
            {!submitted && (
                <Button
                    onClick={handleSubmit}
                    disabled={selectedOption === null}
                    className="w-full"
                >
                    Check answer
                </Button>
            )}
        </div>
    );
}
