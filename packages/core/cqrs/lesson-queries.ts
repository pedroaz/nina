import { connectDatabase } from "../database/database";
import { Lesson, LessonModel } from "../entities/lesson";
import { DatabaseError, ValidationError } from "../errors";

export async function getLessonsByUserId(
    userId: string,
): Promise<Lesson[]> {
    if (!userId) {
        throw new ValidationError('User ID is required');
    }

    try {
        await connectDatabase();
        return await LessonModel.find({ 'studentData.userId': userId })
            .sort({ createdAt: -1 })
            .lean()
            .exec();
    } catch (error) {
        throw new DatabaseError(`Failed to fetch lessons for user: ${userId}`, error);
    }
}

export async function getLessonById(
    lessonId: string
): Promise<Lesson | null> {
    if (!lessonId) {
        throw new ValidationError('Lesson ID is required');
    }

    try {
        await connectDatabase();
        return await LessonModel.findById(lessonId).lean().exec();
    } catch (error) {
        throw new DatabaseError(`Failed to fetch lesson: ${lessonId}`, error);
    }
}