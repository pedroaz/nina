import { connectDatabase } from "../database/database";
import { UserModel } from "../entities/user";
import { LessonModel } from "../entities/lesson";
import { ExerciseSetModel } from "../entities/exercise-set";
import { FlashCardDeckModel } from "../entities/flashcard-deck";
import { FlashCardProgressModel } from "../entities/flashcard-progress";
import { ExerciseSubmissionModel } from "../entities/exercise-submission";
import { PromptMetadataModel } from "../entities/prompt-metadata";
import { MissionModel } from "../entities/mission";
import { MissionChatModel } from "../entities/mission-chat";

export interface CollectionStats {
    collection: string;
    count: number;
}

export interface DatabaseClearResult {
    deletedCollections: CollectionStats[];
    totalDeleted: number;
    timestamp: Date;
}

/**
 * Get counts for all collections before clearing
 */
export async function getDatabaseStatsCommand(): Promise<CollectionStats[]> {
    await connectDatabase();

    const stats: CollectionStats[] = [
        { collection: 'users', count: await UserModel.countDocuments() },
        { collection: 'lessons', count: await LessonModel.countDocuments() },
        { collection: 'exerciseSets', count: await ExerciseSetModel.countDocuments() },
        { collection: 'flashCardDecks', count: await FlashCardDeckModel.countDocuments() },
        { collection: 'flashCardProgress', count: await FlashCardProgressModel.countDocuments() },
        { collection: 'exerciseSubmissions', count: await ExerciseSubmissionModel.countDocuments() },
        { collection: 'promptmetadata', count: await PromptMetadataModel.countDocuments() },
        { collection: 'missions', count: await MissionModel.countDocuments() },
        { collection: 'missionchats', count: await MissionChatModel.countDocuments() },
    ];

    return stats;
}

/**
 * Clear all database collections
 * WARNING: This is a destructive operation - use with extreme caution
 */
export async function clearAllDatabaseTablesCommand(): Promise<DatabaseClearResult> {
    await connectDatabase();

    // Get stats before deletion
    const statsBefore = await getDatabaseStatsCommand();

    // Delete all documents from each collection
    await Promise.all([
        UserModel.deleteMany({}).exec(),
        LessonModel.deleteMany({}).exec(),
        ExerciseSetModel.deleteMany({}).exec(),
        FlashCardDeckModel.deleteMany({}).exec(),
        FlashCardProgressModel.deleteMany({}).exec(),
        ExerciseSubmissionModel.deleteMany({}).exec(),
        PromptMetadataModel.deleteMany({}).exec(),
        MissionModel.deleteMany({}).exec(),
        MissionChatModel.deleteMany({}).exec(),
    ]);

    const totalDeleted = statsBefore.reduce((sum, stat) => sum + stat.count, 0);

    return {
        deletedCollections: statsBefore,
        totalDeleted,
        timestamp: new Date(),
    };
}
