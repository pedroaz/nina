import { NextResponse } from 'next/server';
import { getServerSession } from 'next-auth';
import { authOptions } from '@/app/api/auth/[...nextauth]/route';
import { getUserByEmail } from '@core/index';

export async function GET() {
    const session = await getServerSession(authOptions);

    if (!session?.user?.email) {
        return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }

    const user = await getUserByEmail(session.user.email);

    if (!user) {
        return NextResponse.json({ error: 'User not found' }, { status: 404 });
    }

    return NextResponse.json({
        _id: user._id,
        name: user.name,
        email: user.email,
        level: user.level,
        baseLanguage: user.baseLanguage,
        targetLanguage: user.targetLanguage,
        flashCardDisplayPreference: user.flashCardDisplayPreference,
    });
}
