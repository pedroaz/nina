'use client';

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import logger from "@/lib/logger"
import { BookA } from 'lucide-react';

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

type SentenceCreationExercise = {
    _id: string;
    prompt: DualLanguage;
    referenceAnswer: string;
    context?: string;
};

type Submission = {
    userId: string;
    exerciseId: string;
    answer: string | string[];
    isCorrect: boolean;
    submittedAt: Date;
};

type ExerciseSet = {
    _id: string;
    title: string;
    topic: string;
    type: 'multiple_choice' | 'sentence_creation';
    exercises: (MultipleChoiceExercise | SentenceCreationExercise)[];
    submissions?: Submission[];
};

type SubmissionResult = {
    isCorrect?: boolean;
    score?: number;
    feedback?: string;
};

export default function ExercisePracticePage() {
    const params = useParams();
    const router = useRouter();
    const setId = params.setId as string;

    const [exerciseSet, setExerciseSet] = useState<ExerciseSet | null>(null);
    const [loading, setLoading] = useState(true);
    const [currentIndex, setCurrentIndex] = useState(0);
    const [showTranslation, setShowTranslation] = useState(false);

    // Multiple choice state
    const [selectedOption, setSelectedOption] = useState<number | null>(null);
    const [mcSubmitted, setMcSubmitted] = useState(false);
    const [mcResult, setMcResult] = useState<SubmissionResult | null>(null);

    // Sentence creation state
    const [userSentence, setUserSentence] = useState("");
    const [scSubmitting, setScSubmitting] = useState(false);
    const [scResult, setScResult] = useState<SubmissionResult | null>(null);

    useEffect(() => {
        fetchExerciseSet();
    }, [setId]);

    const fetchExerciseSet = async () => {
        try {
            const response = await fetch(`/api/exercise-sets/${setId}`);
            if (!response.ok) throw new Error('Failed to fetch exercise set');
            const data = await response.json();
            logger.info('Fetched exercise set:', data);

            // Ensure exercises array exists
            if (!data.exercises || !Array.isArray(data.exercises)) {
                throw new Error('Invalid exercise set data');
            }

            setExerciseSet(data);
        } catch (error) {
            console.error('Error fetching exercise set:', error);
        } finally {
            setLoading(false);
        }
    };

    const handleMultipleChoiceSubmit = async () => {
        if (selectedOption === null || !exerciseSet) return;

        const exercise = exerciseSet.exercises[currentIndex] as MultipleChoiceExercise;

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

            const result = await response.json();
            setMcResult(result);
            setMcSubmitted(true);
        } catch (error) {
            console.error('Error submitting answer:', error);
            alert(`Error: ${error instanceof Error ? error.message : 'Failed to submit answer'}`);
        }
    };

    const handleSentenceCreationSubmit = async () => {
        if (!userSentence.trim() || !exerciseSet) return;

        const exercise = exerciseSet.exercises[currentIndex] as SentenceCreationExercise;
        setScSubmitting(true);

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

            const result = await response.json();
            setScResult(result);
        } catch (error) {
            console.error('Error submitting answer:', error);
            alert(`Error: ${error instanceof Error ? error.message : 'Failed to submit answer'}`);
        } finally {
            setScSubmitting(false);
        }
    };

    const handleNext = () => {
        if (!exerciseSet) return;

        if (currentIndex < exerciseSet.exercises.length - 1) {
            setCurrentIndex(currentIndex + 1);
            resetExerciseState();
        } else {
            // Completed all exercises
            router.push('/exercises');
        }
    };

    const resetExerciseState = () => {
        setShowTranslation(false);
        setSelectedOption(null);
        setMcSubmitted(false);
        setMcResult(null);
        setUserSentence("");
        setScResult(null);
    };

    if (loading) {
        return (
            <div className="flex min-h-[60vh] items-center justify-center">
                <p>Loading exercises...</p>
            </div>
        );
    }

    if (!exerciseSet || !exerciseSet.exercises || exerciseSet.exercises.length === 0) {
        return (
            <div className="flex min-h-[60vh] items-center justify-center">
                <p>Exercise set not found or has no exercises</p>
            </div>
        );
    }

    const currentExercise = exerciseSet.exercises[currentIndex];
    const progress = ((currentIndex + 1) / exerciseSet.exercises.length) * 100;

    return (
        <section className="mx-auto flex min-h-[60vh] w-full max-w-4xl flex-col gap-6 px-4 py-10">
            {/* Header */}
            <div>
                <div className="flex items-center gap-2 mb-2">
                    <h1 className="text-2xl font-semibold">{exerciseSet.title}</h1>
                    <Badge>
                        {exerciseSet.type === 'multiple_choice' ? 'Multiple Choice' : 'Sentence Creation'}
                    </Badge>
                </div>
            </div>

            {/* Progress */}
            <div className="space-y-2">
                <div className="flex justify-between text-sm text-neutral-600">
                    <span>Exercise {currentIndex + 1} of {exerciseSet.exercises.length}</span>
                    <span>{Math.round(progress)}% complete</span>
                </div>
                <Progress value={progress} className="h-2" />
            </div>

            {/* Exercise Content */}
            <Card>
                <CardHeader>
                    <div className="flex justify-between items-start">
                        <CardTitle className="text-lg">
                            {exerciseSet.type === 'multiple_choice' ? 'Question' : 'Prompt'}
                        </CardTitle>
                        <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => setShowTranslation(!showTranslation)}
                        >
                            <BookA />
                        </Button>
                    </div>
                </CardHeader>
                <CardContent className="space-y-6">
                    {/* Question/Prompt */}
                    <div className="space-y-2">
                        {exerciseSet.type === 'multiple_choice' ? (
                            <>
                                <p className="text-lg font-medium">
                                    {(currentExercise as MultipleChoiceExercise).question.target}
                                </p>
                                {showTranslation && (
                                    <p className="text-sm text-neutral-600">
                                        {(currentExercise as MultipleChoiceExercise).question.base}
                                    </p>
                                )}
                            </>
                        ) : (
                            <>
                                <p className="text-lg font-medium">
                                    {(currentExercise as SentenceCreationExercise).prompt.target}
                                </p>
                                {showTranslation && (
                                    <p className="text-sm text-neutral-600">
                                        {(currentExercise as SentenceCreationExercise).prompt.base}
                                    </p>
                                )}
                                {(currentExercise as SentenceCreationExercise).context && (
                                    <p className="text-sm italic text-neutral-500">
                                        {(currentExercise as SentenceCreationExercise).context}
                                    </p>
                                )}
                            </>
                        )}
                    </div>

                    {/* Multiple Choice Options */}
                    {exerciseSet.type === 'multiple_choice' && (
                        <div className="space-y-2">
                            {(currentExercise as MultipleChoiceExercise).options.map((option, index) => {
                                const isSelected = selectedOption === index;
                                const isCorrect = index === (currentExercise as MultipleChoiceExercise).correctOptionIndex;
                                const showResult = mcSubmitted;

                                let buttonClass = "w-full justify-start text-left h-auto p-4 ";
                                if (showResult) {
                                    if (isCorrect) {
                                        buttonClass += "border-success-border bg-success-bg hover:bg-success-bg";
                                    } else if (isSelected && !isCorrect) {
                                        buttonClass += "border-error-border bg-error-bg hover:bg-error-bg";
                                    }
                                } else if (isSelected) {
                                    buttonClass += "border-orange-500 bg-orange-50";
                                }

                                return (
                                    <Button
                                        key={index}
                                        className={buttonClass}
                                        onClick={() => {
                                            if (!mcSubmitted) {
                                                setSelectedOption(index);
                                            }
                                        }}
                                        disabled={mcSubmitted}
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
                    )}

                    {/* Sentence Creation Input */}
                    {exerciseSet.type === 'sentence_creation' && !scResult && (
                        <div className="space-y-4">
                            <textarea
                                value={userSentence}
                                onChange={(e) => setUserSentence(e.target.value)}
                                className="min-h-32 w-full rounded-md border border-neutral-200 bg-white p-3 text-sm shadow-sm focus:border-neutral-300 focus:outline-none focus:ring-2 focus:ring-neutral-200"
                                placeholder="Write your sentence here..."
                                disabled={scSubmitting}
                            />
                            <Button
                                onClick={handleSentenceCreationSubmit}
                                disabled={!userSentence.trim() || scSubmitting}
                                className="w-full"
                            >
                                {scSubmitting ? 'Judging your answer...' : 'Submit answer'}
                            </Button>
                        </div>
                    )}

                    {/* Sentence Creation Result */}
                    {exerciseSet.type === 'sentence_creation' && scResult && (
                        <div className="space-y-4">
                            <div className="rounded-lg border border-neutral-200 bg-neutral-50 p-4">
                                <p className="text-sm font-medium text-neutral-700 mb-2">Your answer:</p>
                                <p className="text-base">{userSentence}</p>
                            </div>

                            <div className={`rounded-lg border p-4 ${(scResult.score || 0) >= 80 ? 'border-success-border bg-success-bg' :
                                (scResult.score || 0) >= 60 ? 'border-yellow-200 bg-yellow-50' :
                                    'border-error-border bg-error-bg'
                                }`}>
                                <div className="flex items-center justify-between mb-2">
                                    <span className="text-sm font-medium">Score</span>
                                    <span className="text-2xl font-bold">{scResult.score}/100</span>
                                </div>
                                <p className="text-sm mt-3">{scResult.feedback}</p>
                            </div>

                            <div className="rounded-lg border border-teal-200 bg-teal-50 p-4">
                                <p className="text-sm font-medium text-teal-900 mb-2">Reference answer:</p>
                                <p className="text-sm text-teal-700">
                                    {(currentExercise as SentenceCreationExercise).referenceAnswer}
                                </p>
                            </div>
                        </div>
                    )}

                    {/* Action Buttons */}
                    <div className="flex justify-between pt-4">
                        <Button
                            onClick={() => router.push('/exercises')}
                        >
                            Back to exercises
                        </Button>

                        {exerciseSet.type === 'multiple_choice' && !mcSubmitted && (
                            <Button
                                onClick={handleMultipleChoiceSubmit}
                                disabled={selectedOption === null}
                            >
                                Check answer
                            </Button>
                        )}

                        {(mcSubmitted || scResult) && (
                            <Button onClick={handleNext}>
                                {currentIndex < exerciseSet.exercises.length - 1 ? 'Next exercise' : 'Finish'}
                            </Button>
                        )}
                    </div>
                </CardContent>
            </Card>
        </section>
    );
}
