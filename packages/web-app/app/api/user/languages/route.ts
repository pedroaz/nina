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
    const { baseLanguage, targetLanguage } = body || {};

    const validLanguages = ['english', 'german', 'spanish', 'french', 'italian', 'portuguese'];

    // Validate baseLanguage if provided
    if (baseLanguage && !validLanguages.includes(baseLanguage)) {
        return NextResponse.json(
            { error: `Invalid base language. Must be one of: ${validLanguages.join(', ')}` },
            { status: 400 }
        );
    }

    // Validate targetLanguage if provided
    if (targetLanguage && !validLanguages.includes(targetLanguage)) {
        return NextResponse.json(
            { error: `Invalid target language. Must be one of: ${validLanguages.join(', ')}` },
            { status: 400 }
        );
    }

    // Ensure baseLanguage and targetLanguage are not the same
    const finalBaseLanguage = baseLanguage || user.baseLanguage;
    const finalTargetLanguage = targetLanguage || user.targetLanguage;

    if (finalBaseLanguage === finalTargetLanguage) {
        return NextResponse.json(
            { error: 'Base language and target language must be different' },
            { status: 400 }
        );
    }

    // Build update object with only provided fields
    const updateFields: any = {};
    if (baseLanguage) updateFields.baseLanguage = baseLanguage;
    if (targetLanguage) updateFields.targetLanguage = targetLanguage;

    const updatedUser = await UserModel.findByIdAndUpdate(
        user._id,
        updateFields,
        { new: true }
    );

    return NextResponse.json(updatedUser);
}
