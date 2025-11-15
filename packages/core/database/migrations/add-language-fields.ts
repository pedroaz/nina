/**
 * Migration script to add baseLanguage and targetLanguage fields to existing users
 *
 * This script updates all existing users to have:
 * - baseLanguage: 'english' (default)
 * - targetLanguage: 'german' (default)
 *
 * Run this script once after deploying the multi-language feature.
 */

import { connectDatabase } from "../database";
import { UserModel } from "../../entities/user";

export async function migrateUserLanguages() {
    try {
        await connectDatabase();

        console.log('[Migration] Starting user language field migration...');

        // Update all users that don't have baseLanguage or targetLanguage set
        const result = await UserModel.updateMany(
            {
                $or: [
                    { baseLanguage: { $exists: false } },
                    { targetLanguage: { $exists: false } }
                ]
            },
            {
                $set: {
                    baseLanguage: 'english',
                    targetLanguage: 'german'
                }
            }
        );

        console.log(`[Migration] Updated ${result.modifiedCount} users`);
        console.log('[Migration] Migration completed successfully');

        return {
            success: true,
            modifiedCount: result.modifiedCount
        };
    } catch (error) {
        console.error('[Migration] Error during migration:', error);
        throw error;
    }
}

// Allow running this script directly
if (require.main === module) {
    migrateUserLanguages()
        .then((result) => {
            console.log('Migration result:', result);
            process.exit(0);
        })
        .catch((error) => {
            console.error('Migration failed:', error);
            process.exit(1);
        });
}
