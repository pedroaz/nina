import Link from "next/link";
import { redirect } from "next/navigation";
import { getServerSession } from "next-auth";
import { authOptions } from "@/app/api/auth/[...nextauth]/route";
import { getFlashCardDecksByUserId, getUserByEmail, getDeckProgressSummary } from "@core/index";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { DeckCard } from "@/components/deck-card";

type DeckListItem = {
    id: string;
    title: string;
    cardCount: number;
    knownCards: number;
    totalCards: number;
    sourceLesson?: string;
};

export default async function FlashCards() {
    const session = await getServerSession(authOptions);
    const signInUrl = `/api/auth/signin?callbackUrl=${encodeURIComponent("/flash-cards")}`;

    if (!session?.user?.email) {
        redirect(signInUrl);
    }

    const user = await getUserByEmail(session.user.email);

    if (!user) {
        redirect(signInUrl);
    }

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

    return (
        <section className="mx-auto flex min-h-[60vh] w-full max-w-5xl flex-col gap-8 px-4 py-10">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                <div>
                    <h1 className="text-3xl font-semibold">Flash Card Decks</h1>
                    <p className="mt-2 text-neutral-600">
                        Practice and memorize Language with interactive flash cards.
                    </p>
                </div>
                <Button asChild>
                    <Link href="/flash-cards/new">Create new deck</Link>
                </Button>
            </div>

            {deckItems.length === 0 ? (
                <Card className="border-dashed border-neutral-300 shadow-none hover:shadow-none hover:translate-y-0 bg-neutral-50">
                    <div className="p-12 text-center text-neutral-500">
                        <p className="text-lg font-medium">You don&apos;t have any flash card decks yet.</p>
                        <p className="mt-2 text-sm">
                            Create a deck to start practicing vocabulary and phrases.
                        </p>
                    </div>
                </Card>
            ) : (
                <div className="grid gap-4 md:grid-cols-2">
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
            )}
        </section>
    );
}
