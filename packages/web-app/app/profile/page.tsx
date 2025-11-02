import { redirect } from "next/navigation";
import { getServerSession } from "next-auth";

import { authOptions } from "@/app/api/auth/[...nextauth]/route";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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
    const displayLevel = user.level || "Not set";

    return (
        <section className="mx-auto flex min-h-[60vh] w-full max-w-3xl flex-col gap-8 px-4 py-10">
            <header>
                <h1 className="text-3xl font-semibold">Your profile</h1>
                <p className="mt-2 text-sm text-slate-500">
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
                            <dt className="text-xs font-medium uppercase text-slate-500">
                                Name
                            </dt>
                            <dd className="text-base text-slate-800">{displayName}</dd>
                        </div>
                        <div>
                            <dt className="text-xs font-medium uppercase text-slate-500">
                                Level
                            </dt>
                            <dd className="text-base text-slate-800">{displayLevel}</dd>
                        </div>
                        <div className="sm:col-span-2">
                            <dt className="text-xs font-medium uppercase text-slate-500">
                                Email
                            </dt>
                            <dd className="text-base text-slate-800">
                                {session.user.email}
                            </dd>
                        </div>
                    </dl>
                </CardContent>
            </Card>
        </section>
    );
}
