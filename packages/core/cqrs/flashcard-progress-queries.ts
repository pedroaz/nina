import { connectDatabase } from "../database/database";
import { FlashCardProgress, FlashCardProgressModel } from "../entities/flashcard-progress";

export async function getProgressByDeckAndUser(
    deckId: string,
    userId: string
): Promise<FlashCardProgress | null> {
    await connectDatabase();
    return FlashCardProgressModel.findOne({
        deckId: deckId,
        userId: userId,
    }).lean().exec();
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
}
