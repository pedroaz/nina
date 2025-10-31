import { Lesson, LessonModel } from "@core/entities/lesson";
import { connectDatabase } from "../database/database";

export interface CreateLessonRequestData {
    creatorId: string;
    prompt: string;
    lessonId?: string | null;
}

export async function createLessonCommand(
    data: CreateLessonRequestData,
): Promise<Lesson> {
    await connectDatabase();
    const lesson = new LessonModel({
        creatorId: data.creatorId,
        prompt: data.prompt,
        lessonId: data.lessonId ?? null,
    });

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
