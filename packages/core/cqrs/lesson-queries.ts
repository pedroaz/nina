import { connectDatabase } from "../database/database";
import { Lesson, LessonModel } from "../entities/lesson";

export async function getLessonsByUserId(
    userId: string,
): Promise<Lesson[]> {
    await connectDatabase();
    console.log('Fetching lessons for userId:', userId);
    return LessonModel.find({ 'studentData.userId': userId })
        .sort({ createdAt: -1 })
        .lean()
        .exec();
}

export async function getLessonById(
    lessonId: string
): Promise<Lesson | null> {
    await connectDatabase();
    return LessonModel.findById(lessonId).lean().exec();
}