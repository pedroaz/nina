import { connectDatabase } from "../database/database";
import { Lesson, LessonModel } from "../entities/lesson";
import { createLessonFlow } from "../llm/llm";
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
            preferredLanguage: "english",
            studentLevel: user.level,
        },
    });

    var llmResult = await createLessonFlow({
        topic: data.topic,
        vocabulary: data.vocabulary,
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
