import { NextResponse } from "next/server";
import { getServerSession } from "next-auth";
import { authOptions } from "@/app/api/auth/[...nextauth]/route";
import { getUserByEmail } from "@core/index";
import { connectDatabase } from "@core/database/database";
import { PromptMetadataModel } from "@core/entities/prompt-metadata";

export async function GET() {
    const session = await getServerSession(authOptions);

    if (!session?.user?.email) {
        return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    const user = await getUserByEmail(session.user.email);

    if (!user) {
        return NextResponse.json({ error: "User not found" }, { status: 404 });
    }

    try {
        await connectDatabase();

        // Aggregate usage data for this user
        const usageData = await PromptMetadataModel.aggregate([
            { $match: { userId: user._id.toString() } },
            {
                $group: {
                    _id: null,
                    totalInputTokens: { $sum: "$inputTokens" },
                    totalOutputTokens: { $sum: "$outputTokens" },
                    totalTokens: { $sum: "$totalTokens" },
                    totalCost: { $sum: "$totalCost" },
                    totalInputCost: { $sum: "$inputCost" },
                    totalOutputCost: { $sum: "$outputCost" },
                    operationCount: { $sum: 1 },
                },
            },
        ]);

        // Get breakdown by operation type
        const operationBreakdown = await PromptMetadataModel.aggregate([
            { $match: { userId: user._id.toString() } },
            {
                $group: {
                    _id: "$operation",
                    count: { $sum: 1 },
                    totalTokens: { $sum: "$totalTokens" },
                    totalCost: { $sum: "$totalCost" },
                },
            },
            { $sort: { totalCost: -1 } },
        ]);

        // Get breakdown by model
        const modelBreakdown = await PromptMetadataModel.aggregate([
            { $match: { userId: user._id.toString() } },
            {
                $group: {
                    _id: "$modelUsed",
                    count: { $sum: 1 },
                    totalTokens: { $sum: "$totalTokens" },
                    totalCost: { $sum: "$totalCost" },
                },
            },
            { $sort: { totalCost: -1 } },
        ]);

        const summary = usageData.length > 0 ? usageData[0] : {
            totalInputTokens: 0,
            totalOutputTokens: 0,
            totalTokens: 0,
            totalCost: 0,
            totalInputCost: 0,
            totalOutputCost: 0,
            operationCount: 0,
        };

        return NextResponse.json({
            summary,
            operationBreakdown,
            modelBreakdown,
        });
    } catch (error) {
        console.error('[Usage API] Error fetching usage data:', error);
        return NextResponse.json(
            { error: "Failed to fetch usage data" },
            { status: 500 }
        );
    }
}
