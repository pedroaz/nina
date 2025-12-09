import { NextRequest, NextResponse } from "next/server";
import { getServerSession } from "next-auth";
import { authOptions } from "@/app/api/auth/[...nextauth]/route";
import { appendExtraSectionCommand, getUserByEmail } from "@core/index";

export async function POST(req: NextRequest, context: { params: Promise<{ id: string }> }) {
    const session = await getServerSession(authOptions);

    if (!session?.user?.email) {
        return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    const user = await getUserByEmail(session.user.email);

    if (!user) {
        return NextResponse.json({ error: "User not found" }, { status: 404 });
    }

    const { id } = await context.params;
    const { request } = await req.json();

    if (!request) {
        return NextResponse.json({ error: "Request is required" }, { status: 400 });
    }

    try {
        const updatedLesson = await appendExtraSectionCommand({
            lessonId: id,
            request,
        });

        return NextResponse.json(updatedLesson, { status: 200 });
    } catch (error) {
        console.error('Failed to append extra section:', error);
        return NextResponse.json({ error: "Failed to append extra section" }, { status: 500 });
    }
}
