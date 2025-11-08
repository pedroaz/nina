import { connectDatabase } from "../database/database";
import { FlashCardProgress, FlashCardProgressModel } from "../entities/flashcard-progress";

export interface UpdateCardProgressRequestData {
    deckId: string;
    userId: string;
    cardId: string;
    answer: 'know' | 'dontKnow';
}

export async function updateCardProgressCommand(
    data: UpdateCardProgressRequestData,
): Promise<FlashCardProgress> {
    await connectDatabase();

    // Find or create progress document for this deck/user combination
    let progress = await FlashCardProgressModel.findOne({
        deckId: data.deckId,
        userId: data.userId,
    });

    if (!progress) {
        // Create new progress document
        progress = new FlashCardProgressModel({
            deckId: data.deckId,
            userId: data.userId,
            cardProgress: [],
        });
    }

    // Find or create progress for this specific card
    const cardProgressIndex = progress.cardProgress.findIndex(
        cp => cp.cardId === data.cardId
    );

    if (cardProgressIndex === -1) {
        // Card not tracked yet, add it
        progress.cardProgress.push({
            cardId: data.cardId,
            knowCount: data.answer === 'know' ? 1 : 0,
            dontKnowCount: data.answer === 'dontKnow' ? 1 : 0,
            lastAnswer: data.answer,
        });
    } else {
        // Update existing card progress
        const cardProgress = progress.cardProgress[cardProgressIndex];
        if (data.answer === 'know') {
            cardProgress.knowCount += 1;
        } else {
            cardProgress.dontKnowCount += 1;
        }
        cardProgress.lastAnswer = data.answer;
    }

    await progress.save();
    return progress;
}

export interface GetOrCreateProgressRequestData {
    deckId: string;
    userId: string;
}

export async function getOrCreateProgressCommand(
    data: GetOrCreateProgressRequestData,
): Promise<FlashCardProgress> {
    await connectDatabase();

    let progress = await FlashCardProgressModel.findOne({
        deckId: data.deckId,
        userId: data.userId,
    });

    if (!progress) {
        progress = new FlashCardProgressModel({
            deckId: data.deckId,
            userId: data.userId,
            cardProgress: [],
        });
        await progress.save();
    }

    return progress;
}
