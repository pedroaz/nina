import { connectDatabase } from "../database/database";
import { FlashCardDeck, FlashCardDeckModel } from "../entities/flashcard-deck";
import { DatabaseError, ValidationError } from "../errors";

export async function getFlashCardDecksByUserId(
    userId: string,
): Promise<FlashCardDeck[]> {
    if (!userId) {
        throw new ValidationError('User ID is required');
    }

    try {
        await connectDatabase();
        return await FlashCardDeckModel.find({ 'studentData.userId': userId })
            .sort({ createdAt: -1 })
            .lean()
            .exec();
    } catch (error) {
        throw new DatabaseError(`Failed to fetch flashcard decks for user: ${userId}`, error);
    }
}

export async function getFlashCardDeckById(
    deckId: string
): Promise<FlashCardDeck | null> {
    if (!deckId) {
        throw new ValidationError('Deck ID is required');
    }

    try {
        await connectDatabase();
        return await FlashCardDeckModel.findById(deckId).lean().exec();
    } catch (error) {
        throw new DatabaseError(`Failed to fetch flashcard deck: ${deckId}`, error);
    }
}
