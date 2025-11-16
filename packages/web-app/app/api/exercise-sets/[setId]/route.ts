import { NextResponse } from "next/server";
import { getServerSession } from "next-auth";
import { authOptions } from "@/app/api/auth/[...nextauth]/route";
import {
    getExerciseSetByIdQuery,
    deleteExerciseSetCommand,
    getUserByEmail,
    getExerciseSubmissionsBySetAndUserQuery,
} from "@core/index";

export async function GET(
    req: Request,
    { params }: { params: Promise<{ setId: string }> }
) {
    const { setId } = await params;
    const session = await getServerSession(authOptions);

    if (!session?.user?.email) {
        return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    const user = await getUserByEmail(session.user.email);

    if (!user) {
        return NextResponse.json({ error: "User not found" }, { status: 404 });
    }

    const exerciseSet = await getExerciseSetByIdQuery(setId);

    if (!exerciseSet) {
        return NextResponse.json({ error: "Exercise set not found" }, { status: 404 });
    }

    // Get user's submissions for this set
    const submissions = await getExerciseSubmissionsBySetAndUserQuery(
        setId,
        user._id
    );

    // Serialize the Mongoose document properly
    const serializedSet = JSON.parse(JSON.stringify(exerciseSet));

    return NextResponse.json({
        ...serializedSet,
        submissions,
    });
}

export async function DELETE(
    req: Request,
    { params }: { params: Promise<{ setId: string }> }
) {
    const { setId } = await params;
    const session = await getServerSession(authOptions);

    if (!session?.user?.email) {
        return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    const user = await getUserByEmail(session.user.email);

    if (!user) {
        return NextResponse.json({ error: "User not found" }, { status: 404 });
    }

    const exerciseSet = await getExerciseSetByIdQuery(setId);

    if (!exerciseSet) {
        return NextResponse.json({ error: "Exercise set not found" }, { status: 404 });
    }

    // Verify ownership
    if (exerciseSet.studentData.userId !== user._id) {
        return NextResponse.json({ error: "Forbidden" }, { status: 403 });
    }

    await deleteExerciseSetCommand({ setId });

    return NextResponse.json({ success: true });
}
