import Link from "next/link";
import { redirect } from "next/navigation";
import { getServerSession } from "next-auth";
import { authOptions } from "@/app/api/auth/[...nextauth]/route";
import { getFlashCardDecksByUserId, getUserByEmail, getDeckProgressSummary } from "@core/index";
import { Button } from "@/components/ui/button";
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
                    <p className="mt-2 text-slate-600">
                        Practice and memorize German with interactive flash cards.
                    </p>
                </div>
                <Button asChild>
                    <Link href="/flash-cards/new">Create new deck</Link>
                </Button>
            </div>

            {deckItems.length === 0 ? (
                <div className="rounded-xl border border-dashed border-slate-200 p-12 text-center text-slate-500">
                    <p>You don&apos;t have any flash card decks yet.</p>
                    <p className="mt-2 text-sm">
                        Create a deck to start practicing German vocabulary and phrases.
                    </p>
                </div>
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
