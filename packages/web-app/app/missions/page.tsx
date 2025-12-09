import Link from "next/link";
import { Suspense } from "react";
import { getMissionsByUserId } from "@core/index";
import { Button } from "@/components/ui/button";
import { PentagonSpinner } from "@/components/pentagon-spinner";
import {
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Trash2, Play, CheckCircle2 } from "lucide-react";

export default function MissionsPage() {
    return (
        <section className="mx-auto flex min-h-[60vh] w-full max-w-5xl flex-col gap-8 px-4 py-10">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                <div>
                    <h1 className="text-3xl font-semibold">Missions</h1>
                    <p className="text-neutral-600 mt-2">
                        Practice real-world scenarios and improve your conversation skills.
                    </p>
                </div>
                <Button asChild>
                    <Link href="/missions/new">Create new</Link>
                </Button>
            </div>
            <Suspense fallback={<PentagonSpinner />}>
                <MissionList />
            </Suspense>
        </section>
    );
}

async function MissionList() {
    const { getAuthenticatedUser } = await import("@/lib/get-authenticated-user");
    const user = await getAuthenticatedUser("/missions");

    const missions = await getMissionsByUserId(user._id);

    if (missions.length === 0) {
        return (
            <Card className="border-dashed border-neutral-300 shadow-none hover:shadow-none hover:translate-y-0 bg-neutral-50">
                <div className="p-12 text-center text-neutral-500">
                    <p className="text-lg font-medium">You have not created any missions yet.</p>
                    <p className="mt-2 text-sm">
                        Create a mission to practice a specific scenario.
                    </p>
                </div>
            </Card>
        );
    }

    return (
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
            {missions.map((mission) => (
                <Card key={mission._id.toString()} className="flex flex-col">
                    <CardHeader>
                        <div className="flex items-center justify-between mb-2">
                            <CardTitle className="text-xl">{mission.title}</CardTitle>
                            <Badge variant="teal">
                                {mission.difficulty}
                            </Badge>
                        </div>
                    </CardHeader>
                    <CardContent className="flex-1 flex flex-col justify-between gap-4">
                        <div>
                            <h4 className="text-sm font-semibold mb-2">Objectives:</h4>
                            <ul className="text-sm text-neutral-600 space-y-2">
                                {mission.objectives.map((obj, idx) => (
                                    <li key={idx} className="flex items-start gap-2">
                                        <CheckCircle2 className="size-4 text-success mt-0.5 shrink-0" />
                                        <span>{obj}</span>
                                    </li>
                                ))}
                            </ul>
                        </div>
                        <div className="flex gap-2 mt-4">
                            <form action={`/api/missions/${mission._id}`} method="post">
                                <Button variant="destructive" size="icon" type="submit">
                                    <Trash2 className="size-4" />
                                </Button>
                            </form>
                            <Button asChild className="flex-1">
                                <Link href={`/missions/${mission._id}`}>
                                    <Play className="mr-2 size-4" /> Start Mission
                                </Link>
                            </Button>
                        </div>
                    </CardContent>
                </Card>
            ))}
        </div>
    );
}
