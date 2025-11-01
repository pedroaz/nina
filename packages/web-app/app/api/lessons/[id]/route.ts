import { NextResponse } from "next/server";
import { revalidatePath } from "next/cache";
import { getServerSession } from "next-auth";
import { authOptions } from "@/app/api/auth/[...nextauth]/route";
import { deleteLessonCommand, getUserByEmail } from "@core/index";

function shouldReturnJson(acceptHeader: string | null) {
    if (!acceptHeader) {
        return false;
    }

    return acceptHeader.split(",").some((value) => value.trim().startsWith("application/json"));
}

async function deleteLessonById(req: Request, lessonId: string | undefined) {
    if (!lessonId) {
        return NextResponse.json({ error: "Lesson id is required" }, { status: 400 });
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
        await deleteLessonCommand({ requestId: lessonId });
    } catch (error) {
        return NextResponse.json({ error: "Failed to delete lesson" }, { status: 500 });
    }

    revalidatePath("/lessons");

    if (shouldReturnJson(req.headers.get("accept"))) {
        return NextResponse.json({ success: true }, { status: 200 });
    }

    const redirectUrl = new URL("/lessons", req.url);
    return NextResponse.redirect(redirectUrl);
}

export async function POST(req: Request, { params }: { params: { id?: string } }) {
    return deleteLessonById(req, params.id);
}

export async function DELETE(req: Request, { params }: { params: { id?: string } }) {
    return deleteLessonById(req, params.id);
}
