import { redirect } from "next/navigation";
import { getServerSession } from "next-auth";

import { authOptions } from "@/app/api/auth/[...nextauth]/route";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { FlashCardSettings } from "@/components/flash-card-settings";
import { LevelSettings } from "@/components/level-settings";
import { LanguageSettings } from "@/components/language-settings";
import { SignOutButton } from "@/components/sign-out-button";
import { getUserByEmail } from "@core/index";

export default async function Profile() {
    const session = await getServerSession(authOptions);
    const signInUrl = `/api/auth/signin?callbackUrl=${encodeURIComponent("/profile")}`;

    if (!session?.user?.email) {
        redirect(signInUrl);
    }

    const user = await getUserByEmail(session.user.email);

    if (!user) {
        redirect(signInUrl);
    }

    const displayName = user.name || session.user.name || "Anonymous";
    const userLevel = user.level || "A1";

    // Get flash card preference from user
    const flashCardPreference = user.flashCardDisplayPreference || 'base-first';

    // Get language preferences from user
    const baseLanguage = (user.baseLanguage || 'english') as 'english' | 'portuguese';
    const targetLanguage = (user.targetLanguage || 'german') as 'german' | 'french' | 'spanish' | 'italian';

    return (
        <section className="mx-auto flex min-h-[60vh] w-full max-w-3xl flex-col gap-8 px-4 py-10">
            <header>
                <h1 className="text-3xl font-semibold">Your profile</h1>
                <p className="mt-2 text-sm text-neutral-500">
                    Keep track of your learning details in one place.
                </p>
            </header>

            <Card>
                <CardHeader>
                    <CardTitle>Account details</CardTitle>
                </CardHeader>
                <CardContent>
                    <dl className="grid gap-4 sm:grid-cols-2">
                        <div>
                            <dt className="text-xs font-medium uppercase text-neutral-500">
                                Name
                            </dt>
                            <dd className="text-base text-neutral-900">{displayName}</dd>
                        </div>
                        <div className="sm:col-span-2">
                            <dt className="text-xs font-medium uppercase text-neutral-500">
                                Email
                            </dt>
                            <dd className="text-base text-neutral-900">
                                {session.user.email}
                            </dd>
                        </div>
                    </dl>
                    <div className="mt-6">
                        <SignOutButton />
                    </div>
                </CardContent>
            </Card>

            <Card>
                <CardHeader>
                    <CardTitle>Language Preferences</CardTitle>
                </CardHeader>
                <CardContent>
                    <LanguageSettings
                        initialBaseLanguage={baseLanguage}
                        initialTargetLanguage={targetLanguage}
                    />
                </CardContent>
            </Card>

            <Card>
                <CardHeader>
                    <CardTitle>Learning Level</CardTitle>
                </CardHeader>
                <CardContent>
                    <LevelSettings initialLevel={userLevel} />
                </CardContent>
            </Card>

            <Card>
                <CardHeader>
                    <CardTitle>Flash Card Preferences</CardTitle>
                </CardHeader>
                <CardContent>
                    <FlashCardSettings
                        initialPreference={flashCardPreference}
                        baseLanguage={baseLanguage}
                        targetLanguage={targetLanguage}
                    />
                </CardContent>
            </Card>
        </section>
    );
}
