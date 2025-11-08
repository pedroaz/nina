import { NextResponse } from "next/server";
import { getServerSession } from "next-auth";
import { authOptions } from "@/app/api/auth/[...nextauth]/route";
import {
    getFlashCardDeckById,
    deleteFlashCardDeckCommand,
    getUserByEmail,
    getProgressByDeckAndUser,
} from "@core/index";

export async function GET(
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

    // Get progress for this deck
    const progress = await getProgressByDeckAndUser(deckId, user._id);

    return NextResponse.json({
        deck,
        progress: progress || { cardProgress: [] },
    });
}

export async function DELETE(
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

    await deleteFlashCardDeckCommand({ deckId: deckId });

    return NextResponse.json({ success: true });
}
