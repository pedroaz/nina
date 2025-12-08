import { NextResponse } from "next/server";
import { getServerSession } from "next-auth";
import { authOptions } from "@/app/api/auth/[...nextauth]/route";
import { clearAllDatabaseTablesCommand, getDatabaseStatsCommand, logger } from "@core/index";

const ADMIN_EMAIL = "nina-app@outlook.com";

/**
 * GET - Get current database statistics
 */
export async function GET() {
    const session = await getServerSession(authOptions);

    // Auth check
    if (!session?.user?.email || session.user.email !== ADMIN_EMAIL) {
        return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    try {
        const stats = await getDatabaseStatsCommand();
        return NextResponse.json({ stats });
    } catch (error) {
        logger.error('[Admin API] Error getting database stats:', error);
        return NextResponse.json(
            { error: "Failed to get database statistics" },
            { status: 500 }
        );
    }
}

/**
 * DELETE - Clear all database tables
 */
export async function DELETE() {
    const session = await getServerSession(authOptions);

    // Auth check
    if (!session?.user?.email || session.user.email !== ADMIN_EMAIL) {
        return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    try {
        logger.info(`[Admin API] CLEARING DATABASE - Initiated by: ${session.user.email}`);
        const result = await clearAllDatabaseTablesCommand();
        logger.info(`[Admin API] Database cleared - Total deleted: ${result.totalDeleted}`);

        return NextResponse.json(result);
    } catch (error) {
        logger.error('[Admin API] Error clearing database:', error);
        return NextResponse.json(
            { error: "Failed to clear database" },
            { status: 500 }
        );
    }
}
