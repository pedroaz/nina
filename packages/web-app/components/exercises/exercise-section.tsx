import { ExerciseSet } from "@core/index";
import { Badge } from "@/components/ui/badge";
import { ExerciseSetCard } from "./exercise-set-card";

interface ExerciseSectionProps {
    title: string;
    exerciseSets: ExerciseSet[];
}

export function ExerciseSection({ title, exerciseSets }: ExerciseSectionProps) {
    if (exerciseSets.length === 0) {
        return null;
    }

    return (
        <div>
            <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
                {title}
                <Badge variant="teal">{exerciseSets.length}</Badge>
            </h2>
            <div className="grid gap-4 md:grid-cols-2">
                {exerciseSets.map((set) => (
                    <ExerciseSetCard key={set._id} exerciseSet={set} />
                ))}
            </div>
        </div>
    );
}
