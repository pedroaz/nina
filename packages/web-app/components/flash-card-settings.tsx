'use client';

import { useState } from "react";
import { Label } from "@/components/ui/label";

interface FlashCardSettingsProps {
    initialPreference: 'base-first' | 'target-first';
}

export function FlashCardSettings({ initialPreference }: FlashCardSettingsProps) {
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
            <p className="text-sm text-slate-600">
                Choose which language to show first when practicing flash cards.
            </p>
            <div className="space-y-2">
                <label className="flex items-center gap-3 rounded-lg border border-slate-200 p-4 cursor-pointer hover:bg-slate-50 transition-colors">
                    <input
                        type="radio"
                        name="flashCardDisplay"
                        value="base-first"
                        checked={preference === 'base-first'}
                        onChange={() => handleChange('base-first')}
                        disabled={isSaving}
                        className="h-4 w-4 text-blue-600 focus:ring-blue-500"
                    />
                    <div>
                        <p className="font-medium">English First</p>
                        <p className="text-sm text-slate-600">
                            Show English text first, flip to reveal
                        </p>
                    </div>
                </label>
                <label className="flex items-center gap-3 rounded-lg border border-slate-200 p-4 cursor-pointer hover:bg-slate-50 transition-colors">
                    <input
                        type="radio"
                        name="flashCardDisplay"
                        value="target-first"
                        checked={preference === 'target-first'}
                        onChange={() => handleChange('target-first')}
                        disabled={isSaving}
                        className="h-4 w-4 text-blue-600 focus:ring-blue-500"
                    />
                    <div>
                        <p className="font-medium">Target First</p>
                        <p className="text-sm text-slate-600">
                            Show Target text first, flip to reveal English
                        </p>
                    </div>
                </label>
            </div>
            {isSaving && (
                <p className="text-sm text-blue-600">Saving...</p>
            )}
        </div>
    );
}
