import { connectDatabase } from "../database/database";
import { FlashCardDeck, FlashCardDeckModel, FlashCard } from "../entities/flashcard-deck";
import { getUserById } from "./user-queries";
import { getLessonById } from "./lesson-queries";
import { generateFlashCardsFromPromptFlow, generateFlashCardsFromLessonFlow } from "../llm/llm";

export interface CreateFlashCardDeckRequestData {
    userId: string;
    title: string;
    cards: FlashCard[];
    sourceLesson?: string;
}

export async function createFlashCardDeckCommand(
    data: CreateFlashCardDeckRequestData,
): Promise<FlashCardDeck> {
    await connectDatabase();
    const user = await getUserById(data.userId);

    if (!user) throw new Error('User not found');

    const deckObject = new FlashCardDeckModel({
        title: data.title,
        studentData: {
            userId: user._id,
            userName: user.name,
            preferredLanguage: user.baseLanguage,
            studentLevel: user.level,
        },
        cards: data.cards,
        sourceLesson: data.sourceLesson,
    });

    await deckObject.save();
    return deckObject;
}

export interface GenerateFlashCardDeckFromPromptRequestData {
    userId: string;
    topic: string;
    cardCount: number;
}

export async function generateFlashCardDeckFromPromptCommand(
    data: GenerateFlashCardDeckFromPromptRequestData,
): Promise<FlashCardDeck> {
    await connectDatabase();
    const user = await getUserById(data.userId);

    if (!user) throw new Error('User not found');

    // Generate cards using LLM
    const llmResult = await generateFlashCardsFromPromptFlow({
        topic: data.topic,
        cardCount: data.cardCount,
        studentLevel: user.level,
        baseLanguage: user.baseLanguage,
        targetLanguage: user.targetLanguage,
    });

    if (!llmResult || !llmResult.cards || llmResult.cards.length === 0) {
        throw new Error('Failed to generate flash cards');
    }

    // Create deck with generated cards
    const deckObject = new FlashCardDeckModel({
        title: llmResult.title,
        studentData: {
            userId: user._id,
            userName: user.name,
            preferredLanguage: user.baseLanguage,
            studentLevel: user.level,
        },
        cards: llmResult.cards,
    });

    await deckObject.save();
    return deckObject;
}

export interface GenerateFlashCardDeckFromLessonRequestData {
    userId: string;
    lessonId: string;
    cardCount: number;
    deckTitle: string;
}

export async function generateFlashCardDeckFromLessonCommand(
    data: GenerateFlashCardDeckFromLessonRequestData,
): Promise<FlashCardDeck> {
    await connectDatabase();
    const user = await getUserById(data.userId);
    if (!user) throw new Error('User not found');

    const lesson = await getLessonById(data.lessonId);
    if (!lesson) throw new Error('Lesson not found');

    // Serialize lesson for LLM (convert ObjectIds to strings)
    const serializedLesson = {
        _id: lesson._id.toString(),
        __v: lesson.__v,
        topic: lesson.topic,
        vocabulary: lesson.vocabulary || '',
        studentData: {
            userId: lesson.studentData.userId.toString(),
            userName: lesson.studentData.userName,
            preferredLanguage: lesson.studentData.preferredLanguage,
            studentLevel: lesson.studentData.studentLevel,
        },
        title: lesson.title,
        quickSummary: lesson.quickSummary,
        quickExamples: lesson.quickExamples,
        fullExplanation: lesson.fullExplanation,
        extraSections: lesson.extraSections || [],
    };

    // Generate cards using LLM based on lesson content
    const llmResult = await generateFlashCardsFromLessonFlow({
        lesson: serializedLesson,
        cardCount: data.cardCount,
        studentLevel: user.level,
        baseLanguage: user.baseLanguage,
        targetLanguage: user.targetLanguage,
    });

    if (!llmResult || !llmResult.cards || llmResult.cards.length === 0) {
        throw new Error('Failed to generate flash cards from lesson');
    }

    // Create deck with generated cards
    const deckObject = new FlashCardDeckModel({
        title: data.deckTitle,
        studentData: {
            userId: user._id,
            userName: user.name,
            preferredLanguage: user.baseLanguage,
            studentLevel: user.level,
        },
        cards: llmResult.cards,
        sourceLesson: data.lessonId,
    });

    await deckObject.save();
    return deckObject;
}

export interface DeleteFlashCardDeckRequestData {
    deckId: string;
}

export async function deleteFlashCardDeckCommand(
    data: DeleteFlashCardDeckRequestData,
): Promise<void> {
    await connectDatabase();
    await FlashCardDeckModel.deleteOne({
        _id: data.deckId,
    }).exec();
}
