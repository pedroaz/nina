'use client';

import { useState } from "react";
import { Label } from "@/components/ui/label";

interface FlashCardSettingsProps {
    initialPreference: 'base-first' | 'target-first';
    baseLanguage?: string;
    targetLanguage?: string;
}

export function FlashCardSettings({ initialPreference, baseLanguage = 'Base', targetLanguage = 'Target' }: FlashCardSettingsProps) {
    // Capitalize first letter for display
    const baseLanguageDisplay = baseLanguage.charAt(0).toUpperCase() + baseLanguage.slice(1);
    const targetLanguageDisplay = targetLanguage.charAt(0).toUpperCase() + targetLanguage.slice(1);
    const [preference, setPreference] = useState(initialPreference);
    const [isSaving, setIsSaving] = useState(false);

    const handleChange = async (newPreference: 'base-first' | 'target-first') => {
        setPreference(newPreference);
        setIsSaving(true);

        try {
            await fetch('/api/user/settings', {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    flashCardDisplayPreference: newPreference,
                }),
            });
        } catch (error) {
            console.error('Failed to update settings:', error);
            // Revert on error
            setPreference(initialPreference);
        } finally {
            setIsSaving(false);
        }
    };

    return (
        <div className="space-y-4">
            <Label>Flash Card Display</Label>
            <p className="text-sm text-neutral-600">
                Choose which language to show first when practicing flash cards.
            </p>
            <div className="space-y-2">
                <label className="flex items-center gap-3 rounded-lg border border-neutral-200 p-4 cursor-pointer hover:bg-neutral-50 transition-colors">
                    <input
                        type="radio"
                        name="flashCardDisplay"
                        value="base-first"
                        checked={preference === 'base-first'}
                        onChange={() => handleChange('base-first')}
                        disabled={isSaving}
                        className="h-4 w-4 text-teal-600 focus:ring-teal-500"
                    />
                    <div>
                        <p className="font-medium">{baseLanguageDisplay} First</p>
                        <p className="text-sm text-neutral-600">
                            Show {baseLanguageDisplay} text first, flip to reveal {targetLanguageDisplay}
                        </p>
                    </div>
                </label>
                <label className="flex items-center gap-3 rounded-lg border border-neutral-200 p-4 cursor-pointer hover:bg-neutral-50 transition-colors">
                    <input
                        type="radio"
                        name="flashCardDisplay"
                        value="target-first"
                        checked={preference === 'target-first'}
                        onChange={() => handleChange('target-first')}
                        disabled={isSaving}
                        className="h-4 w-4 text-teal-600 focus:ring-teal-500"
                    />
                    <div>
                        <p className="font-medium">{targetLanguageDisplay} First</p>
                        <p className="text-sm text-neutral-600">
                            Show {targetLanguageDisplay} text first, flip to reveal {baseLanguageDisplay}
                        </p>
                    </div>
                </label>
            </div>
            {isSaving && (
                <p className="text-sm text-teal-600">Saving...</p>
            )}
        </div>
    );
}
