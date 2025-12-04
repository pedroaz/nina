import { connectDatabase } from "../database/database";
import { Lesson, LessonModel } from "../entities/lesson";
import { createLessonFlow, appendExtraSectionFlow } from "../llm/llm";
import { getUserById } from "./user-queries";
import { savePromptMetadataCommand } from "./prompt-metadata-commands";
import { ValidationError, NotFoundError, DatabaseError, ExternalServiceError } from "../errors";

export interface CreateLessonRequestData {
    userId: string;
    topic: string;
    vocabulary: string;
    modelType?: 'fast' | 'detailed';
    focus?: 'vocabulary' | 'grammar';
    image?: string;
}

export async function createLessonCommand(
    data: CreateLessonRequestData,
): Promise<Lesson> {
    if (!data.userId) {
        throw new ValidationError('User ID is required');
    }
    if (!data.topic?.trim()) {
        throw new ValidationError('Topic is required');
    }
    if (!data.vocabulary?.trim()) {
        throw new ValidationError('Vocabulary is required');
    }

    try {
        await connectDatabase();
        const user = await getUserById(data.userId);

        if (!user) {
            throw new NotFoundError(`User not found: ${data.userId}`);
        }

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

        if (!llmResult) {
            throw new ExternalServiceError('Failed to generate lesson from LLM');
        }

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
    } catch (error) {
        if (error instanceof ValidationError || error instanceof NotFoundError || error instanceof ExternalServiceError) {
            throw error;
        }
        throw new DatabaseError('Failed to create lesson', error);
    }
}

export interface DeleteLessonRequestData {
    requestId: string;
}

export async function deleteLessonCommand(
    data: DeleteLessonRequestData,
): Promise<void> {
    if (!data.requestId) {
        throw new ValidationError('Lesson ID is required');
    }

    try {
        await connectDatabase();
        const result = await LessonModel.deleteOne({
            _id: data.requestId,
        }).exec();

        if (result.deletedCount === 0) {
            throw new NotFoundError(`Lesson not found: ${data.requestId}`);
        }
    } catch (error) {
        if (error instanceof ValidationError || error instanceof NotFoundError) {
            throw error;
        }
        throw new DatabaseError(`Failed to delete lesson: ${data.requestId}`, error);
    }
}

export interface AppendExtraSectionRequestData {
    lessonId: string;
    request: string;
}

export async function appendExtraSectionCommand(
    data: AppendExtraSectionRequestData,
): Promise<Lesson> {
    if (!data.lessonId) {
        throw new ValidationError('Lesson ID is required');
    }
    if (!data.request?.trim()) {
        throw new ValidationError('Request is required');
    }

    try {
        await connectDatabase();

        const lesson = await LessonModel.findById(data.lessonId);
        if (!lesson) {
            throw new NotFoundError(`Lesson not found: ${data.lessonId}`);
        }

        const user = await getUserById(lesson.studentData.userId);
        if (!user) {
            throw new NotFoundError(`User not found: ${lesson.studentData.userId}`);
        }

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

        if (!extraSection) {
            throw new ExternalServiceError('Failed to generate extra section from LLM');
        }

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
    } catch (error) {
        if (error instanceof ValidationError || error instanceof NotFoundError || error instanceof ExternalServiceError) {
            throw error;
        }
        throw new DatabaseError('Failed to append extra section', error);
    }
}
