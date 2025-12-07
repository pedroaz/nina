import { redirect } from "next/navigation";
import { getServerSession } from "next-auth";

import { authOptions } from "@/app/api/auth/[...nextauth]/route";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { AdminDatabasePanel } from "@/components/admin-database-panel";

const ADMIN_EMAIL = "nina-app@outlook.com";

export default async function AdminPage() {
    const session = await getServerSession(authOptions);
    const signInUrl = `/api/auth/signin?callbackUrl=${encodeURIComponent("/admin")}`;

    // Auth check - must be signed in
    if (!session?.user?.email) {
        redirect(signInUrl);
    }

    // Admin check - must be the specific admin email
    if (session.user.email !== ADMIN_EMAIL) {
        redirect("/");
    }

    return (
        <section className="mx-auto flex min-h-[60vh] w-full max-w-3xl flex-col gap-8 px-4 py-10">
            <header>
                <h1 className="text-3xl font-semibold">Admin Panel</h1>
                <p className="mt-2 text-neutral-600">
                    System administration and database management.
                </p>
            </header>

            <Card>
                <CardHeader>
                    <CardTitle>Admin Information</CardTitle>
                </CardHeader>
                <CardContent>
                    <dl className="grid gap-4">
                        <div>
                            <dt className="text-xs font-medium uppercase text-neutral-500">
                                Logged in as
                            </dt>
                            <dd className="text-base text-neutral-900">
                                {session.user.email}
                            </dd>
                        </div>
                        <div>
                            <dt className="text-xs font-medium uppercase text-neutral-500">
                                Role
                            </dt>
                            <dd className="text-base text-neutral-900">
                                System Administrator
                            </dd>
                        </div>
                    </dl>
                </CardContent>
            </Card>

            <AdminDatabasePanel />
        </section>
    );
}
