import { connectDatabase } from "../database/database";
import { Lesson, LessonModel } from "../entities/lesson";
import { createLessonFlow } from "../llm/llm";

export interface CreateLessonRequestData {
    creatorId: string;
    userPrompt: string;
}

export async function createLessonCommand(
    data: CreateLessonRequestData,
): Promise<Lesson> {
    await connectDatabase();
    const lesson = new LessonModel({
        creatorId: data.creatorId,
        prompt: data.userPrompt,
    });

    var llmResult = await createLessonFlow({
        userPrompt: data.userPrompt,
    });

    if (!llmResult) throw new Error('Failed to generate lesson');

    lesson.title = llmResult.title;
    lesson.germanContent = llmResult.germanContent;
    lesson.englishContent = llmResult.englishContent;

    await lesson.save();


    return lesson;
}

export interface DeleteLessonRequestData {
    requestId: string;
    creatorId: string;
}

export async function deleteLessonCommand(
    data: DeleteLessonRequestData,
): Promise<void> {
    await connectDatabase();
    await LessonModel.deleteOne({
        _id: data.requestId,
        creatorId: data.creatorId,
    }).exec();
}
