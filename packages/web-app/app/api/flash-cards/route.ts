import { NextResponse } from "next/server";
import { getServerSession } from "next-auth";
import { authOptions } from "@/app/api/auth/[...nextauth]/route";
import {
    generateFlashCardDeckFromPromptCommand,
    generateFlashCardDeckFromLessonCommand,
    createFlashCardDeckCommand,
    getFlashCardDecksByUserId,
    getUserByEmail,
    getDeckProgressSummary,
} from "@core/index";

export async function POST(req: Request) {
    const session = await getServerSession(authOptions);

    if (!session?.user?.email) {
        return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    const body = await req.json().catch(() => null);
    const { type, topic, cardCount, lessonId, deckTitle, cards, sourceLesson } = body || {};

    const user = await getUserByEmail(session.user.email);

    if (!user) {
        return NextResponse.json({ error: "User not found" }, { status: 404 });
    }

    const startTime = performance.now();

    try {
        let deck;

        if (type === 'from-prompt') {
            // Generate deck from topic/prompt
            if (!topic || !cardCount) {
                return NextResponse.json(
                    { error: "Topic and card count are required" },
                    { status: 400 }
                );
            }

            console.log(`[Flash Cards API] Generating deck from prompt for user: ${user.email}`);
            console.log(`[Flash Cards API] Topic: "${topic}", Cards: ${cardCount}`);

            deck = await generateFlashCardDeckFromPromptCommand({
                userId: user._id,
                topic,
                cardCount: parseInt(cardCount),
            });
        } else if (type === 'from-lesson') {
            // Generate deck from lesson
            if (!lessonId || !cardCount || !deckTitle) {
                return NextResponse.json(
                    { error: "Lesson ID, deck title, and card count are required" },
                    { status: 400 }
                );
            }

            console.log(`[Flash Cards API] Generating deck from lesson for user: ${user.email}`);
            console.log(`[Flash Cards API] Lesson ID: ${lessonId}, Cards: ${cardCount}`);

            deck = await generateFlashCardDeckFromLessonCommand({
                userId: user._id,
                lessonId,
                cardCount: parseInt(cardCount),
                deckTitle,
            });
        } else if (type === 'manual') {
            // Manual deck creation
            if (!deckTitle || !cards || !Array.isArray(cards)) {
                return NextResponse.json(
                    { error: "Deck title and cards array are required" },
                    { status: 400 }
                );
            }

            console.log(`[Flash Cards API] Creating manual deck for user: ${user.email}`);

            deck = await createFlashCardDeckCommand({
                userId: user._id,
                title: deckTitle,
                cards,
                sourceLesson,
            });
        } else {
            return NextResponse.json(
                { error: "Invalid type. Must be 'from-prompt', 'from-lesson', or 'manual'" },
                { status: 400 }
            );
        }

        const totalTime = performance.now() - startTime;
        console.log(`[Flash Cards API] Deck created in ${totalTime.toFixed(2)}ms`);

        return NextResponse.json(deck, { status: 201 });
    } catch (error) {
        console.error('[Flash Cards API] Error creating deck:', error);
        return NextResponse.json(
            { error: "Failed to create flash card deck" },
            { status: 500 }
        );
    }
}

export async function GET() {
    const session = await getServerSession(authOptions);

    if (!session?.user?.email) {
        return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    const user = await getUserByEmail(session.user.email);

    if (!user) {
        return NextResponse.json({ error: "User not found" }, { status: 404 });
    }

    const decks = await getFlashCardDecksByUserId(user._id);

    // Enhance decks with progress summaries
    const decksWithProgress = await Promise.all(
        decks.map(async (deck) => {
            const progress = await getDeckProgressSummary(
                deck._id,
                user._id,
                deck.cards.length
            );
            return {
                ...deck,
                progress,
            };
        })
    );

    return NextResponse.json({ data: decksWithProgress });
}
