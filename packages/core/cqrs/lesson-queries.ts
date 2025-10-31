import { Lesson, LessonModel } from "@core/entities/lesson";
import { connectDatabase } from "../database/database";

export async function getLessonsByCreatorId(
    creatorId: string,
): Promise<Lesson[]> {
    await connectDatabase();
    return LessonModel.find({ creatorId })
        .sort({ createdAt: -1 })
        .exec();
}

export async function getLessonByIdAndCreator(
    lessonId: string,
    creatorId: string,
): Promise<Lesson | null> {
    await connectDatabase();

    return LessonModel.findOne({ _id: lessonId, creatorId }).exec();
}
