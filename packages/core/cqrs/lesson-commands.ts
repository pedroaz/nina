import { connectDatabase } from "../database/database";
import { Lesson, LessonModel } from "../entities/lesson";
import { createLessonFlow, appendExtraSectionFlow } from "../llm/llm";
import { getUserById } from "./user-queries";
import { savePromptMetadataCommand } from "./prompt-metadata-commands";

export interface CreateLessonRequestData {
    userId?: string;
    topic: string;
    vocabulary: string;
    modelType?: 'fast' | 'detailed';
    focus?: 'vocabulary' | 'grammar';
    image?: string;
}

export async function createLessonCommand(
    data: CreateLessonRequestData,
): Promise<Lesson> {
    await connectDatabase();
    const user = await getUserById(data.userId!); // ensure user exists

    if (!user) throw new Error('User not found');

    // Call LLM with model type and get usage metadata
    const { lesson: llmResult, usage } = await createLessonFlow({
        topic: data.topic,
        vocabulary: data.vocabulary,
        baseLanguage: user.baseLanguage,
        targetLanguage: user.targetLanguage,
        modelType: data.modelType,
        focus: data.focus,
        image: data.image,
    });

    if (!llmResult) throw new Error('Failed to generate lesson');

    // Create lesson object
    const lessonObject = new LessonModel({
        topic: data.topic,
        vocabulary: data.vocabulary,
        studentData: {
            userId: user._id,
            userName: user.name,
            preferredLanguage: user.baseLanguage,
            studentLevel: user.level,
        },
        title: llmResult.title,
        quickSummary: llmResult.quickSummary,
        quickExamples: llmResult.quickExamples,
        fullExplanation: llmResult.fullExplanation,
        modelUsed: usage.modelUsed as 'gpt-5-nano' | 'gpt-4o-mini',
    });

    // Save lesson first to get the ID
    await lessonObject.save();

    // Save prompt metadata
    const promptMetadata = await savePromptMetadataCommand({
        lessonId: lessonObject._id.toString(),
        operation: 'lesson_creation',
        modelUsed: usage.modelUsed as 'gpt-5-nano' | 'gpt-4o-mini',
        inputTokens: usage.inputTokens,
        outputTokens: usage.outputTokens,
        totalTokens: usage.totalTokens,
        userId: user._id.toString(),
        executionTimeMs: usage.executionTimeMs,
        finishReason: usage.finishReason,
    });

    // Update lesson with prompt metadata reference
    lessonObject.creationPromptMetadataId = promptMetadata._id.toString();
    await lessonObject.save();

    return lessonObject;
}

export interface DeleteLessonRequestData {
    requestId: string;
}

export async function deleteLessonCommand(
    data: DeleteLessonRequestData,
): Promise<void> {
    await connectDatabase();
    await LessonModel.deleteOne({
        _id: data.requestId,
    }).exec();
}

export interface AppendExtraSectionRequestData {
    lessonId: string;
    request: string;
}

export async function appendExtraSectionCommand(
    data: AppendExtraSectionRequestData,
): Promise<Lesson> {
    await connectDatabase();

    const lesson = await LessonModel.findById(data.lessonId);
    if (!lesson) throw new Error('Lesson not found');

    const user = await getUserById(lesson.studentData.userId);
    if (!user) throw new Error('User not found');

    const { section: extraSection, usage } = await appendExtraSectionFlow({
        request: data.request,
        lessonContext: {
            topic: lesson.topic,
            vocabulary: lesson.vocabulary,
            title: lesson.title,
            quickSummary: lesson.quickSummary,
            baseLanguage: user.baseLanguage,
            targetLanguage: user.targetLanguage,
        },
    });

    if (!extraSection) throw new Error('Failed to generate extra section');

    if (!lesson.extraSections) {
        lesson.extraSections = [];
    }

    lesson.extraSections.push(extraSection);
    await lesson.save();

    // Save prompt metadata for extra section generation
    await savePromptMetadataCommand({
        lessonId: lesson._id.toString(),
        operation: 'extra_section',
        modelUsed: usage.modelUsed as 'gpt-5-nano' | 'gpt-4o-mini',
        inputTokens: usage.inputTokens,
        outputTokens: usage.outputTokens,
        totalTokens: usage.totalTokens,
        userId: user._id.toString(),
        executionTimeMs: usage.executionTimeMs,
        finishReason: usage.finishReason,
    });

    return lesson;
}
