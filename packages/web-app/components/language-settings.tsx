'use client';

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Label } from "@/components/ui/label";

const BASE_LANGUAGES = [
    { value: 'english', label: 'English' },
    { value: 'portuguese', label: 'Portuguese' },
] as const;

const TARGET_LANGUAGES = [
    { value: 'german', label: 'German' },
    { value: 'french', label: 'French' },
    { value: 'spanish', label: 'Spanish' },
    { value: 'italian', label: 'Italian' },
] as const;

type BaseLanguage = typeof BASE_LANGUAGES[number]['value'];
type TargetLanguage = typeof TARGET_LANGUAGES[number]['value'];

interface LanguageSettingsProps {
    initialBaseLanguage: BaseLanguage;
    initialTargetLanguage: TargetLanguage;
}

export function LanguageSettings({ initialBaseLanguage, initialTargetLanguage }: LanguageSettingsProps) {
    const router = useRouter();
    const [baseLanguage, setBaseLanguage] = useState<BaseLanguage>(initialBaseLanguage);
    const [targetLanguage, setTargetLanguage] = useState<TargetLanguage>(initialTargetLanguage);
    const [isSaving, setIsSaving] = useState(false);

    const handleBaseLanguageChange = async (newBaseLanguage: BaseLanguage) => {
        setBaseLanguage(newBaseLanguage);
        setIsSaving(true);

        try {
            const response = await fetch('/api/user/languages', {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    baseLanguage: newBaseLanguage,
                }),
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Failed to update base language');
            }

            router.refresh();
        } catch (error) {
            console.error('Failed to update base language:', error);
            setBaseLanguage(initialBaseLanguage);
            alert(error instanceof Error ? error.message : 'Failed to update base language');
        } finally {
            setIsSaving(false);
        }
    };

    const handleTargetLanguageChange = async (newTargetLanguage: TargetLanguage) => {
        setTargetLanguage(newTargetLanguage);
        setIsSaving(true);

        try {
            const response = await fetch('/api/user/languages', {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    targetLanguage: newTargetLanguage,
                }),
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Failed to update target language');
            }

            router.refresh();
        } catch (error) {
            console.error('Failed to update target language:', error);
            setTargetLanguage(initialTargetLanguage);
            alert(error instanceof Error ? error.message : 'Failed to update target language');
        } finally {
            setIsSaving(false);
        }
    };

    return (
        <div className="space-y-6">
            {/* Base Language */}
            <div className="space-y-4">
                <Label>Base Language (Your Native Language)</Label>
                <p className="text-sm text-neutral-600">
                    This is the language used for explanations and translations. It should be your most comfortable language.
                </p>
                <div className="grid gap-2 sm:grid-cols-2">
                    {BASE_LANGUAGES.map((langOption) => (
                        <label
                            key={langOption.value}
                            className="flex items-center gap-3 rounded-lg border border-neutral-200 p-4 cursor-pointer hover:bg-neutral-50 transition-colors"
                        >
                            <input
                                type="radio"
                                name="baseLanguage"
                                value={langOption.value}
                                checked={baseLanguage === langOption.value}
                                onChange={() => handleBaseLanguageChange(langOption.value)}
                                disabled={isSaving}
                                className="h-4 w-4 text-teal-600 focus:ring-teal-500"
                            />
                            <div>
                                <p className="font-medium">{langOption.label}</p>
                            </div>
                        </label>
                    ))}
                </div>
            </div>

            {/* Target Language */}
            <div className="space-y-4">
                <Label>Target Language (Language You're Learning)</Label>
                <p className="text-sm text-neutral-600">
                    This is the language you want to learn. All lessons and exercises will focus on this language.
                </p>
                <div className="grid gap-2 sm:grid-cols-2">
                    {TARGET_LANGUAGES.map((langOption) => (
                        <label
                            key={langOption.value}
                            className="flex items-center gap-3 rounded-lg border border-neutral-200 p-4 cursor-pointer hover:bg-neutral-50 transition-colors"
                        >
                            <input
                                type="radio"
                                name="targetLanguage"
                                value={langOption.value}
                                checked={targetLanguage === langOption.value}
                                onChange={() => handleTargetLanguageChange(langOption.value)}
                                disabled={isSaving}
                                className="h-4 w-4 text-teal-600 focus:ring-teal-500"
                            />
                            <div>
                                <p className="font-medium">{langOption.label}</p>
                            </div>
                        </label>
                    ))}
                </div>
            </div>

            {isSaving && (
                <p className="text-sm text-teal-600">Saving...</p>
            )}
        </div>
    );
}
