'use client';

import { useState, useEffect } from "react";
import { FlashCardPractice, SerializedFlashCard } from "./flashcard-practice";

interface FlashCardMiniGameProps {
    className?: string;
}

export function FlashCardMiniGame({ className }: FlashCardMiniGameProps) {
    const [deck, setDeck] = useState<{
        _id: string;
        title: string;
        cards: SerializedFlashCard[];
    } | null>(null);
    const [displayPreference, setDisplayPreference] = useState<'base-first' | 'target-first'>('base-first');
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchRandomDeck = async () => {
            try {
                const response = await fetch('/api/flash-cards');
                if (response.ok) {
                    const decks = await response.json();
                    if (decks.length > 0) {
                        // Pick a random deck
                        const randomDeck = decks[Math.floor(Math.random() * decks.length)];
                        setDeck({
                            _id: randomDeck._id,
                            title: randomDeck.title,
                            cards: randomDeck.cards.map((card: any) => ({
                                _id: card._id.toString(),
                                base: card.base,
                                target: card.target,
                            })),
                        });
                    }
                }
            } catch (error) {
                console.error('Failed to fetch flashcard deck:', error);
            } finally {
                setLoading(false);
            }
        };

        // Fetch user preference
        const fetchUserPreference = async () => {
            try {
                const response = await fetch('/api/user/me');
                if (response.ok) {
                    const userData = await response.json();
                    setDisplayPreference(userData.flashCardDisplayPreference || 'base-first');
                }
            } catch (error) {
                console.error('Failed to fetch user preference:', error);
            }
        };

        fetchRandomDeck();
        fetchUserPreference();
    }, []);

    if (loading) {
        return (
            <div className={className}>
                <p className="text-center text-slate-600">Loading flashcards...</p>
            </div>
        );
    }

    if (!deck || deck.cards.length === 0) {
        return (
            <div className={className}>
                <p className="text-center text-slate-600">No flashcards available. Create some first!</p>
            </div>
        );
    }

    return (
        <FlashCardPractice
            deckId={deck._id}
            deckTitle={deck.title}
            cards={deck.cards}
            displayPreference={displayPreference}
            mode="mini"
            className={className}
        />
    );
}
