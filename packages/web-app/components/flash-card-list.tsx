import { getFlashCardDecksByUserId, getDeckProgressSummary } from "@core/index";
import { Card } from "@/components/ui/card";
import { DeckCard } from "@/components/deck-card";
import { getAuthenticatedUser } from "@/lib/get-authenticated-user";

type DeckListItem = {
    id: string;
    title: string;
    cardCount: number;
    knownCards: number;
    totalCards: number;
    sourceLesson?: string;
};

export async function DeckList() {
    const user = await getAuthenticatedUser("/flash-cards");

    const decks = await getFlashCardDecksByUserId(user._id);

    // Enhance decks with progress
    const deckItems: DeckListItem[] = await Promise.all(
        decks.map(async (deck) => {
            const progress = await getDeckProgressSummary(
                deck._id,
                user._id,
                deck.cards.length
            );
            return {
                id: deck._id.toString(),
                title: deck.title,
                cardCount: deck.cards.length,
                knownCards: progress.knownCards,
                totalCards: progress.totalCards,
                sourceLesson: deck.sourceLesson,
            };
        })
    );

    if (deckItems.length === 0) {
        return (
            <Card className="border-dashed border-neutral-300 shadow-none hover:shadow-none hover:translate-y-0 bg-neutral-50">
                <div className="p-12 text-center text-neutral-500">
                    <p className="text-lg font-medium">You don&apos;t have any flash card decks yet.</p>
                    <p className="mt-2 text-sm">
                        Create a deck to start practicing vocabulary and phrases.
                    </p>
                </div>
            </Card>
        );
    }

    return (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {deckItems.map((deck) => (
                <DeckCard
                    key={deck.id}
                    id={deck.id}
                    title={deck.title}
                    cardCount={deck.cardCount}
                    knownCards={deck.knownCards}
                    totalCards={deck.totalCards}
                    sourceLesson={deck.sourceLesson}
                />
            ))}
        </div>
    );
}
