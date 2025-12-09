import { NextResponse } from "next/server";
import { getServerSession } from "next-auth";
import { authOptions } from "@/app/api/auth/[...nextauth]/route";
import {
    updateCardProgressCommand,
    getUserByEmail,
    getFlashCardDeckById,
} from "@core/index";

export async function POST(
    req: Request,
    { params }: { params: Promise<{ deckId: string }> }
) {
    const { deckId } = await params;
    const session = await getServerSession(authOptions);

    if (!session?.user?.email) {
        return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    const user = await getUserByEmail(session.user.email);

    if (!user) {
        return NextResponse.json({ error: "User not found" }, { status: 404 });
    }

    const deck = await getFlashCardDeckById(deckId);

    if (!deck) {
        return NextResponse.json({ error: "Deck not found" }, { status: 404 });
    }

    // Verify ownership - convert both to strings for comparison
    if (deck.studentData.userId.toString() !== user._id.toString()) {
        return NextResponse.json({ error: "Forbidden" }, { status: 403 });
    }

    const body = await req.json().catch(() => null);
    const { cardId, answer } = body || {};

    if (!cardId || !answer || !['know', 'dontKnow'].includes(answer)) {
        return NextResponse.json(
            { error: "Valid cardId and answer ('know' or 'dontKnow') are required" },
            { status: 400 }
        );
    }

    const progress = await updateCardProgressCommand({
        deckId: deckId,
        userId: user._id,
        cardId,
        answer,
    });

    return NextResponse.json(progress);
}
