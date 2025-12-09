import { NextResponse } from "next/server";
import { getServerSession } from "next-auth";
import { authOptions } from "@/app/api/auth/[...nextauth]/route";
import {
    getUserByEmail,
} from "@core/index";
import { UserModel } from "@core/entities/user";

export async function PATCH(req: Request) {
    const session = await getServerSession(authOptions);

    if (!session?.user?.email) {
        return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    const user = await getUserByEmail(session.user.email);

    if (!user) {
        return NextResponse.json({ error: "User not found" }, { status: 404 });
    }

    const body = await req.json().catch(() => null);
    const { level } = body || {};

    const validLevels = ['A1', 'A2', 'B1', 'B2', 'C1', 'C2'];

    if (!level || !validLevels.includes(level)) {
        return NextResponse.json(
            { error: `Invalid level. Must be one of: ${validLevels.join(', ')}` },
            { status: 400 }
        );
    }

    const updatedUser = await UserModel.findByIdAndUpdate(
        user._id,
        { level },
        { new: true }
    );

    return NextResponse.json(updatedUser);
}
