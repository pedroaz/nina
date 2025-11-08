import { connectDatabase } from "../database/database";
import { FlashCardDeck, FlashCardDeckModel } from "../entities/flashcard-deck";

export async function getFlashCardDecksByUserId(
    userId: string,
): Promise<FlashCardDeck[]> {
    await connectDatabase();
    return FlashCardDeckModel.find({ 'studentData.userId': userId })
        .sort({ createdAt: -1 })
        .lean()
        .exec();
}

export async function getFlashCardDeckById(
    deckId: string
): Promise<FlashCardDeck | null> {
    await connectDatabase();
    return FlashCardDeckModel.findById(deckId).lean().exec();
}
