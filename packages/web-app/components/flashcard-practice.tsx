'use client';

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

// Serialized flash card type (plain objects only)
interface SerializedFlashCard {
    _id: string;
    base: string;
    target: string;
}

interface FlashCardPracticeProps {
    deckId: string;
    deckTitle: string;
    cards: SerializedFlashCard[];
    displayPreference: 'base-first' | 'target-first';
}

export function FlashCardPractice({ deckId, deckTitle, cards, displayPreference }: FlashCardPracticeProps) {
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
        return (
            <div className="mx-auto flex min-h-[60vh] w-full max-w-2xl flex-col items-center justify-center gap-6 px-4 py-10">
                <Card className="w-full">
                    <CardHeader>
                        <CardTitle className="text-center text-2xl">Session Complete!</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-6">
                        <div className="text-center space-y-4">
                            <div className="grid grid-cols-2 gap-4">
                                <div className="rounded-lg bg-green-50 p-4 border border-green-200">
                                    <p className="text-sm text-green-600 font-medium">Known</p>
                                    <p className="text-3xl font-bold text-green-700">{knownCount}</p>
                                </div>
                                <div className="rounded-lg bg-red-50 p-4 border border-red-200">
                                    <p className="text-sm text-red-600 font-medium">Don&apos;t Know</p>
                                    <p className="text-3xl font-bold text-red-700">{unknownCount}</p>
                                </div>
                            </div>
                            <div className="pt-4">
                                <p className="text-slate-600">
                                    You practiced {shuffledCards.length} cards from <span className="font-medium">{deckTitle}</span>
                                </p>
                            </div>
                        </div>
                        <div className="flex gap-4 justify-center">
                            <Button onClick={handlePracticeAgain} size="lg">
                                Practice Again
                            </Button>
                            <Button variant="outline" size="lg" onClick={() => window.location.href = '/flash-cards'}>
                                Back to Decks
                            </Button>
                        </div>
                    </CardContent>
                </Card>
            </div>
        );
    }

    return (
        <div className="mx-auto flex min-h-[60vh] w-full max-w-2xl flex-col gap-6 px-4 py-10">
            <div className="flex items-center justify-between">
                <h1 className="text-2xl font-semibold">{deckTitle}</h1>
                <p className="text-slate-600">
                    Card {currentIndex + 1} of {shuffledCards.length}
                </p>
            </div>

            <Card className="min-h-[300px] cursor-pointer" onClick={handleFlip}>
                <CardContent className="flex items-center justify-center p-12">
                    <div className="text-center space-y-4">
                        <p className="text-sm text-slate-500 uppercase tracking-wide">
                            {isFlipped ? (displayPreference === 'base-first' ? 'Target' : 'English') : (displayPreference === 'base-first' ? 'English' : 'Target')}
                        </p>
                        <p className="text-2xl font-medium leading-relaxed">
                            {isFlipped ? backSide : frontSide}
                        </p>
                        {!isFlipped && (
                            <p className="text-sm text-slate-500 mt-8">
                                Click to flip
                            </p>
                        )}
                    </div>
                </CardContent>
            </Card>

            <div className="flex gap-4 justify-center">
                <Button
                    variant="outline"
                    size="lg"
                    className="w-40"
                    onClick={handleFlip}
                >
                    Flip Card
                </Button>
            </div>

            {isFlipped && (
                <div className="flex gap-4 justify-center">
                    <Button
                        variant="destructive"
                        size="lg"
                        className="w-40"
                        onClick={() => handleAnswer('dontKnow')}
                    >
                        I Don&apos;t Know
                    </Button>
                    <Button
                        variant="default"
                        size="lg"
                        className="w-40 bg-green-600 hover:bg-green-700"
                        onClick={() => handleAnswer('know')}
                    >
                        I Know
                    </Button>
                </div>
            )}
        </div>
    );
}
