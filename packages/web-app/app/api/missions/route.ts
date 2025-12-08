import { NextRequest, NextResponse } from "next/server";
import { getAuthenticatedUser } from "@/lib/get-authenticated-user";
import { createMissionCommand } from "@core/index";

export async function POST(request: NextRequest) {
    try {
        const user = await getAuthenticatedUser();
        const body = await request.json();
        const { topic } = body;

        if (!topic) {
            return NextResponse.json(
                { error: "Topic is required" },
                { status: 400 }
            );
        }

        const mission = await createMissionCommand({
            userId: user._id,
            topic,
        });

        return NextResponse.json(mission, { status: 201 });
    } catch (error: any) {
        console.error("Error creating mission:", error);
        return NextResponse.json(
            { error: error.message || "Failed to create mission" },
            { status: 500 }
        );
    }
}
