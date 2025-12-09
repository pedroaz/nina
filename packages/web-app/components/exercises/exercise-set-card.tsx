import Link from "next/link";
import { ExerciseSet } from "@core/index";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Play, Trash2 } from "lucide-react";

interface ExerciseSetCardProps {
    exerciseSet: ExerciseSet;
}

export function ExerciseSetCard({ exerciseSet }: ExerciseSetCardProps) {
    return (
        <Card>
            <CardHeader className="flex flex-row items-start justify-between gap-4">
                <div className="space-y-1">
                    <CardTitle className="text-base font-medium">
                        {exerciseSet.title}
                    </CardTitle>
                </div>
                <form action={`/api/exercise-sets/${exerciseSet._id}`} method="post">
                    <div className="flex gap-2">
                        <Button variant="destructive" size="icon-sm" type="submit">
                            <Trash2 className="size-4" />
                        </Button>
                        <Button asChild size="sm">
                            <Link href={`/exercises/${exerciseSet._id}`}>
                                <Play className="size-4" />
                            </Link>
                        </Button>
                    </div>
                </form>
            </CardHeader>
            <CardContent className="flex flex-col gap-2 text-sm text-neutral-600">
                <p className="whitespace-pre-wrap leading-relaxed">
                    {exerciseSet.topic || "No topic available."}
                </p>
            </CardContent>
        </Card>
    );
}
