'use client';

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { ArrowLeft, Check, RotateCcw, X, Target, Languages, PartyPopper } from "lucide-react";

// Serialized flash card type (plain objects only)
export interface SerializedFlashCard {
    _id: string;
    base: string;
    target: string;
}

interface FlashCardPracticeProps {
    deckId: string;
    deckTitle: string;
    cards: SerializedFlashCard[];
    displayPreference: 'base-first' | 'target-first';
    onComplete?: () => void;
    className?: string;
    mode?: 'full' | 'mini';
}

export function FlashCardPractice({
    deckId,
    deckTitle,
    cards,
    displayPreference,
    onComplete,
    className,
    mode = 'full'
}: FlashCardPracticeProps) {
    const [shuffledCards, setShuffledCards] = useState<SerializedFlashCard[]>([]);
    const [currentIndex, setCurrentIndex] = useState(0);
    const [isFlipped, setIsFlipped] = useState(false);
    const [sessionComplete, setSessionComplete] = useState(false);
    const [knownCount, setKnownCount] = useState(0);
    const [unknownCount, setUnknownCount] = useState(0);

    // Shuffle cards on mount
    useEffect(() => {
        const shuffled = [...cards].sort(() => Math.random() - 0.5);
        setShuffledCards(shuffled);
    }, [cards]);

    if (shuffledCards.length === 0) {
        return <div className="text-center p-8">Loading...</div>;
    }

    const currentCard = shuffledCards[currentIndex];
    const frontSide = displayPreference === 'base-first' ? currentCard.base : currentCard.target;
    const backSide = displayPreference === 'base-first' ? currentCard.target : currentCard.base;

    const handleFlip = () => {
        setIsFlipped(!isFlipped);
    };

    const handleAnswer = async (answer: 'know' | 'dontKnow') => {
        // Update progress on server
        try {
            await fetch(`/api/flash-cards/${deckId}/progress`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    cardId: currentCard._id,
                    answer,
                }),
            });
        } catch (error) {
            console.error('Failed to update progress:', error);
        }

        // Update local counts
        if (answer === 'know') {
            setKnownCount(knownCount + 1);
        } else {
            setUnknownCount(unknownCount + 1);
        }

        // Move to next card or show summary
        if (currentIndex < shuffledCards.length - 1) {
            setCurrentIndex(currentIndex + 1);
            setIsFlipped(false);
        } else {
            setSessionComplete(true);
            if (onComplete) {
                onComplete();
            }
        }
    };

    const handlePracticeAgain = () => {
        const shuffled = [...cards].sort(() => Math.random() - 0.5);
        setShuffledCards(shuffled);
        setCurrentIndex(0);
        setIsFlipped(false);
        setSessionComplete(false);
        setKnownCount(0);
        setUnknownCount(0);
    };

    if (sessionComplete) {
        if (mode === 'mini') {
            return (
                <div className={cn("flex flex-col items-center justify-center gap-4 p-4", className)}>
                    <h3 className="text-lg font-semibold">Session Complete!</h3>
                    <div className="flex gap-4 text-sm">
                        <span className="text-success-text font-medium">Known: {knownCount}</span>
                        <span className="text-error-text font-medium">Review: {unknownCount}</span>
                    </div>
                    <Button onClick={handlePracticeAgain} size="sm">
                        Practice Again
                    </Button>
                </div>
            );
        }

        return (
            <div className={cn("mx-auto flex min-h-[60vh] w-full max-w-2xl flex-col items-center justify-center gap-6 px-4 py-10", className)}>
                <Card className="w-full bg-white p-8">
                    <h2 className="text-center text-3xl font-extrabold mb-6 text-neutral-900 flex items-center justify-center gap-2">
                        <PartyPopper className="size-8 text-orange-500" /> Session Complete!
                    </h2>
                    <div className="space-y-6">
                        <div className="text-center space-y-4">
                            <div className="grid grid-cols-2 gap-4">
                                <Card className="bg-success-bg p-6 border-success-text">
                                    <p className="text-sm text-success-text font-bold uppercase">Known</p>
                                    <p className="text-4xl font-extrabold text-success-text mt-2">{knownCount}</p>
                                </Card>
                                <Card className="bg-error-bg p-6 border-error-text">
                                    <p className="text-sm text-error-text font-bold uppercase">Don&apos;t Know</p>
                                    <p className="text-4xl font-extrabold text-error-text mt-2">{unknownCount}</p>
                                </Card>
                            </div>
                            <div className="pt-4">
                                <p className="text-neutral-600">
                                    You practiced {shuffledCards.length} cards from <span className="font-medium">{deckTitle}</span>
                                </p>
                            </div>
                        </div>
                        <div className="flex gap-4 justify-center">
                            <Button onClick={handlePracticeAgain} size="lg" className="text-lg px-8">
                                <RotateCcw className="mr-2 size-5" /> Practice Again
                            </Button>
                            <Button
                                onClick={() => window.location.href = '/flash-cards'}
                                size="lg"
                                className="text-lg px-8"
                            >
                                <ArrowLeft className="mr-2 size-5" /> Back to Decks
                            </Button>
                        </div>
                    </div>
                </Card>
            </div>
        );
    }

    const isMini = mode === 'mini';

    return (
        <div className={cn("mx-auto flex w-full flex-col gap-6", !isMini && "min-h-[60vh] max-w-2xl px-4 py-10", className)}>
            <div className="flex items-center justify-between">
                <h1 className={cn("font-extrabold", isMini ? "text-xl" : "text-3xl")}>{deckTitle}</h1>
                <Badge variant="secondary" className="text-base px-3 py-1">
                    {currentIndex + 1} / {shuffledCards.length}
                </Badge>
            </div>

            <Card
                className={cn("bg-white cursor-pointer rounded-3xl hover:translate-y-[-2px] transition-all", isMini ? "min-h-[200px]" : "min-h-[320px]")}
                onClick={handleFlip}
            >
                <div className={cn("flex items-center justify-center h-full", isMini ? "p-6" : "p-12")}>
                    <div className="text-center space-y-4">
                        <p className="text-xs text-neutral-600 font-bold uppercase tracking-widest flex items-center justify-center gap-2">
                            {isFlipped ? (displayPreference === 'base-first' ? <Target className="size-4" /> : <Languages className="size-4" />) : (displayPreference === 'base-first' ? <Languages className="size-4" /> : <Target className="size-4" />)}
                            {isFlipped ? (displayPreference === 'base-first' ? 'Target' : 'English') : (displayPreference === 'base-first' ? 'English' : 'Target')}
                        </p>
                        <p className={cn("font-bold leading-relaxed text-neutral-900", isMini ? "text-2xl" : "text-3xl")}>
                            {isFlipped ? backSide : frontSide}
                        </p>
                        {!isFlipped && (
                            <p className="text-sm text-neutral-500 mt-4 font-semibold">
                                👆 Click to flip
                            </p>
                        )}
                    </div>
                </div>
            </Card>

            <div className="flex gap-4 justify-center">
                {!isFlipped ? (
                    <Button
                        variant="secondary"
                        size="lg"
                        className="text-lg px-8"
                        onClick={handleFlip}
                    >
                        <RotateCcw className="mr-2 size-5" /> Flip Card
                    </Button>
                ) : (
                    <>
                        <Button
                            variant="destructive"
                            size="lg"
                            className="text-lg px-6"
                            onClick={() => handleAnswer('dontKnow')}
                        >
                            <X className="mr-2 size-5" /> I don&apos;t know
                        </Button>
                        <Button
                            size="lg"
                            className="text-lg px-6 bg-success border-success-text hover:bg-success/90"
                            onClick={() => handleAnswer('know')}
                        >
                            <Check className="mr-2 size-5" /> I know it
                        </Button>
                    </>
                )}
            </div>
        </div>
    );
}
