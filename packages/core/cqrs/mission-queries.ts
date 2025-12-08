import { connectDatabase } from "../database/database";
import { Mission, MissionModel } from "../entities/mission";
import { DatabaseError, ValidationError } from "../errors";

export async function getMissionsByUserId(
    userId: string,
): Promise<Mission[]> {
    if (!userId) {
        throw new ValidationError('User ID is required');
    }

    try {
        await connectDatabase();
        return await MissionModel.find({ 'studentData.userId': userId })
            .sort({ createdAt: -1 })
            .lean()
            .exec();
    } catch (error) {
        throw new DatabaseError(`Failed to fetch missions for user: ${userId}`, error);
    }
}

export async function getMissionById(
    missionId: string
): Promise<Mission | null> {
    if (!missionId) {
        throw new ValidationError('Mission ID is required');
    }

    try {
        await connectDatabase();
        return await MissionModel.findById(missionId).lean().exec();
    } catch (error) {
        throw new DatabaseError(`Failed to fetch mission: ${missionId}`, error);
    }
}
