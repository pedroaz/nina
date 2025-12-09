import { NextRequest, NextResponse } from "next/server";
import { revalidatePath } from "next/cache";
import { getServerSession } from "next-auth";
import { authOptions } from "@/app/api/auth/[...nextauth]/route";
import { deleteMissionCommand, getUserByEmail } from "@core/index";

function shouldReturnJson(acceptHeader: string | null) {
    if (!acceptHeader) {
        return false;
    }

    return acceptHeader.split(",").some((value) => value.trim().startsWith("application/json"));
}

async function deleteMissionById(req: Request, missionId: string | undefined) {
    if (!missionId) {
        return NextResponse.json({ error: "Mission id is required" }, { status: 400 });
    }

    const session = await getServerSession(authOptions);

    if (!session?.user?.email) {
        return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    const user = await getUserByEmail(session.user.email);

    if (!user) {
        return NextResponse.json({ error: "User not found" }, { status: 404 });
    }

    try {
        await deleteMissionCommand({ requestId: missionId });
    } catch (error) {
        return NextResponse.json({ error: "Failed to delete mission" }, { status: 500 });
    }

    revalidatePath("/missions");

    if (shouldReturnJson(req.headers.get("accept"))) {
        return NextResponse.json({ success: true }, { status: 200 });
    }

    const redirectUrl = new URL("/missions", req.url);
    return NextResponse.redirect(redirectUrl);
}

export async function POST(req: NextRequest, context: { params: Promise<{ id: string }> }) {
    const { id } = await context.params;
    return deleteMissionById(req, id);
}

export async function DELETE(req: NextRequest, context: { params: Promise<{ id: string }> }) {
    const { id } = await context.params;
    return deleteMissionById(req, id);
}
