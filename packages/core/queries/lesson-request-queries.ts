import { connectDatabase } from "../database/database";
import { type LessonRequest, LessonRequestModel } from "../entities/lesson_request";

export async function getLessonRequestsByCreatorId(
    creatorId: string,
): Promise<LessonRequest[]> {
    await connectDatabase();
    return LessonRequestModel.find({ creatorId })
        .sort({ createdAt: -1 })
        .exec();
}
