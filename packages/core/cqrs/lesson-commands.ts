import { connectDatabase } from "../database/database";
import { Lesson, LessonModel } from "../entities/lesson";
import { createLessonFlow, appendExtraSectionFlow } from "../llm/llm";
import { getUserById } from "./user-queries";

export interface CreateLessonRequestData {
    userId?: string;
    topic: string;
    vocabulary: string;
}

export async function createLessonCommand(
    data: CreateLessonRequestData,
): Promise<Lesson> {
    await connectDatabase();
    const user = await getUserById(data.userId!); // ensure user exists

    if (!user) throw new Error('User not found');
    const lessonObject = new LessonModel({
        topic: data.topic,
        vocabulary: data.vocabulary,
        studentData: {
            userId: user._id,
            userName: user.name,
            preferredLanguage: user.baseLanguage,
            studentLevel: user.level,
        },
    });

    var llmResult = await createLessonFlow({
        topic: data.topic,
        vocabulary: data.vocabulary,
        baseLanguage: user.baseLanguage,
        targetLanguage: user.targetLanguage,
    });

    if (!llmResult) throw new Error('Failed to generate lesson');

    lessonObject.title = llmResult.title;
    lessonObject.quickSummary = llmResult.quickSummary;
    lessonObject.quickExamples = llmResult.quickExamples;
    lessonObject.fullExplanation = llmResult.fullExplanation;

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

    const extraSection = await appendExtraSectionFlow({
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

    return lesson;
}
