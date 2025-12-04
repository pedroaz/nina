import { connectDatabase } from "../database/database";
import { FlashCardProgress, FlashCardProgressModel } from "../entities/flashcard-progress";
import { DatabaseError, ValidationError } from "../errors";

export async function getProgressByDeckAndUser(
    deckId: string,
    userId: string
): Promise<FlashCardProgress | null> {
    if (!deckId) {
        throw new ValidationError('Deck ID is required');
    }
    if (!userId) {
        throw new ValidationError('User ID is required');
    }

    try {
        await connectDatabase();
        return await FlashCardProgressModel.findOne({
            deckId: deckId,
            userId: userId,
        }).lean().exec();
    } catch (error) {
        throw new DatabaseError(`Failed to fetch progress for deck ${deckId} and user ${userId}`, error);
    }
}

export interface DeckProgressSummary {
    totalCards: number;
    knownCards: number;
    unknownCards: number;
    notPracticedCards: number;
}

export async function getDeckProgressSummary(
    deckId: string,
    userId: string,
    totalCardsInDeck: number
): Promise<DeckProgressSummary> {
    if (!deckId) {
        throw new ValidationError('Deck ID is required');
    }
    if (!userId) {
        throw new ValidationError('User ID is required');
    }
    if (typeof totalCardsInDeck !== 'number' || totalCardsInDeck < 0) {
        throw new ValidationError('Total cards must be a non-negative number');
    }

    try {
        await connectDatabase();

        const progress = await FlashCardProgressModel.findOne({
            deckId: deckId,
            userId: userId,
        }).lean().exec();

    if (!progress) {
        return {
            totalCards: totalCardsInDeck,
            knownCards: 0,
            unknownCards: 0,
            notPracticedCards: totalCardsInDeck,
        };
    }

    let knownCards = 0;
    let unknownCards = 0;

    progress.cardProgress.forEach(cp => {
        if (cp.lastAnswer === 'know') {
            knownCards++;
        } else if (cp.lastAnswer === 'dontKnow') {
            unknownCards++;
        }
    });

        const practicedCards = progress.cardProgress.length;
        const notPracticedCards = totalCardsInDeck - practicedCards;

        return {
            totalCards: totalCardsInDeck,
            knownCards,
            unknownCards,
            notPracticedCards,
        };
    } catch (error) {
        throw new DatabaseError(`Failed to fetch progress summary for deck ${deckId}`, error);
    }
}
