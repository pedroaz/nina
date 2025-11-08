'use client';

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Label } from "@/components/ui/label";

const LEVELS = [
    { value: 'A1', label: 'A1', description: 'Beginner' },
    { value: 'A2', label: 'A2', description: 'Elementary' },
    { value: 'B1', label: 'B1', description: 'Intermediate' },
    { value: 'B2', label: 'B2', description: 'Upper Intermediate' },
    { value: 'C1', label: 'C1', description: 'Advanced' },
    { value: 'C2', label: 'C2', description: 'Proficient' },
] as const;

type StudentLevel = typeof LEVELS[number]['value'];

interface LevelSettingsProps {
    initialLevel: StudentLevel;
}

export function LevelSettings({ initialLevel }: LevelSettingsProps) {
    const router = useRouter();
    const [level, setLevel] = useState<StudentLevel>(initialLevel);
    const [isSaving, setIsSaving] = useState(false);

    const handleChange = async (newLevel: StudentLevel) => {
        setLevel(newLevel);
        setIsSaving(true);

        try {
            const response = await fetch('/api/user/level', {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    level: newLevel,
                }),
            });

            if (!response.ok) {
                throw new Error('Failed to update level');
            }

            // Refresh the page to update the server-rendered level display
            router.refresh();
        } catch (error) {
            console.error('Failed to update level:', error);
            // Revert on error
            setLevel(initialLevel);
        } finally {
            setIsSaving(false);
        }
    };

    return (
        <div className="space-y-4">
            <Label>German Proficiency Level</Label>
            <p className="text-sm text-slate-600">
                Select your current German language proficiency level. This helps personalize your learning experience.
            </p>
            <div className="grid gap-2 sm:grid-cols-2">
                {LEVELS.map((levelOption) => (
                    <label
                        key={levelOption.value}
                        className="flex items-center gap-3 rounded-lg border border-slate-200 p-4 cursor-pointer hover:bg-slate-50 transition-colors"
                    >
                        <input
                            type="radio"
                            name="level"
                            value={levelOption.value}
                            checked={level === levelOption.value}
                            onChange={() => handleChange(levelOption.value)}
                            disabled={isSaving}
                            className="h-4 w-4 text-blue-600 focus:ring-blue-500"
                        />
                        <div>
                            <p className="font-medium">{levelOption.label}</p>
                            <p className="text-sm text-slate-600">
                                {levelOption.description}
                            </p>
                        </div>
                    </label>
                ))}
            </div>
            {isSaving && (
                <p className="text-sm text-blue-600">Saving...</p>
            )}
        </div>
    );
}
