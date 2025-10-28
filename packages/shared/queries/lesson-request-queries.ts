import { getDatabase } from "../database/database";
import { LessonRequest, LessonRequestModel } from "../entities/lesson_request";

export async function getLessonRequestsByCreatorId(
    creatorId: string,
): Promise<LessonRequest[]> {

    return LessonRequestModel.find({ creatorId })
        .sort({ createdAt: -1 })
        .exec();
}
