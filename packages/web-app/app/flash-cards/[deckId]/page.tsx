import { redirect } from "next/navigation";
import { getServerSession } from "next-auth";
import { authOptions } from "@/app/api/auth/[...nextauth]/route";
import { getFlashCardDeckById, getUserByEmail } from "@core/index";
import { FlashCardPractice } from "@/components/flashcard-practice";

export default async function FlashCardDeckPage({ params }: { params: Promise<{ deckId: string }> }) {
    const { deckId } = await params;
    const session = await getServerSession(authOptions);
    const signInUrl = `/api/auth/signin?callbackUrl=${encodeURIComponent(`/flash-cards/${deckId}`)}`;

    if (!session?.user?.email) {
        redirect(signInUrl);
    }

    const user = await getUserByEmail(session.user.email);

    if (!user) {
        redirect(signInUrl);
    }

    console.log('[Flash Card Practice] Fetching deck with ID:', deckId);
    const deck = await getFlashCardDeckById(deckId);

    if (!deck) {
        console.log('[Flash Card Practice] Deck not found, redirecting...');
        redirect('/flash-cards');
    }

    console.log('[Flash Card Practice] Deck found:', deck.title);
    console.log('[Flash Card Practice] User ID:', user._id);
    console.log('[Flash Card Practice] Deck owner ID:', deck.studentData.userId);

    // Verify ownership - convert both to strings for comparison
    if (deck.studentData.userId.toString() !== user._id.toString()) {
        console.log('[Flash Card Practice] Ownership verification failed, redirecting...');
        redirect('/flash-cards');
    }

    // Get display preference from user
    const displayPreference = user.flashCardDisplayPreference || 'base-first';

    // Serialize the deck data for the client component
    const serializedCards = deck.cards.map(card => ({
        _id: card._id.toString(),
        base: card.base,
        target: card.target,
    }));

    return (
        <FlashCardPractice
            deckId={deck._id.toString()}
            deckTitle={deck.title}
            cards={serializedCards}
            displayPreference={displayPreference}
        />
    );
}
