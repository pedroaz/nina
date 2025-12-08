'use client';

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import logger from "@/lib/logger"
import { BookA } from 'lucide-react';
import { MultipleChoiceExerciseComponent } from "@/components/exercises/multiple-choice-exercise";
import { SentenceCreationExerciseComponent } from "@/components/exercises/sentence-creation-exercise";

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

type ExerciseSet = {
    _id: string;
    title: string;
    topic: string;
    type: 'multiple_choice' | 'sentence_creation';
    exercises: (MultipleChoiceExercise | SentenceCreationExercise)[];
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
    const [mcSubmitted, setMcSubmitted] = useState(false);
    const [mcResult, setMcResult] = useState<SubmissionResult | null>(null);

    // Sentence creation state
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

    const handleMultipleChoiceResult = (result: SubmissionResult) => {
        setMcResult(result);
        setMcSubmitted(true);
    };

    const handleSentenceCreationResult = (result: SubmissionResult) => {
        setScResult(result);
    };

    const handleNext = () => {
        if (!exerciseSet) return;

        if (currentIndex < exerciseSet.exercises.length - 1) {
            setCurrentIndex(currentIndex + 1);
            resetExerciseState();
        } else {
            router.push('/exercises');
        }
    };

    const resetExerciseState = () => {
        setShowTranslation(false);
        setMcSubmitted(false);
        setMcResult(null);
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
                    <CardTitle className="text-lg">
                        {exerciseSet.type === 'multiple_choice' ? 'Question' : 'Prompt'}
                    </CardTitle>
                </CardHeader>
                <CardContent className="space-y-6">
                    {/* Multiple Choice Exercise */}
                    {exerciseSet.type === 'multiple_choice' && (
                        <MultipleChoiceExerciseComponent
                            exercise={currentExercise as MultipleChoiceExercise}
                            setId={setId}
                            showTranslation={showTranslation}
                            onTranslationToggle={setShowTranslation}
                            onSubmit={handleMultipleChoiceResult}
                            submitted={mcSubmitted}
                            result={mcResult}
                        />
                    )}

                    {/* Sentence Creation Exercise */}
                    {exerciseSet.type === 'sentence_creation' && (
                        <SentenceCreationExerciseComponent
                            exercise={currentExercise as SentenceCreationExercise}
                            setId={setId}
                            showTranslation={showTranslation}
                            onTranslationToggle={setShowTranslation}
                            onSubmit={handleSentenceCreationResult}
                            result={scResult}
                            submitting={scSubmitting}
                        />
                    )}

                    {/* Action Buttons */}
                    <div className="flex justify-between pt-4">
                        <Button
                            onClick={() => router.push('/exercises')}
                        >
                            Back to exercises
                        </Button>

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
