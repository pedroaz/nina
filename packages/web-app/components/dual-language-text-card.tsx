'use client';

import { useState } from 'react';
import type { CSSProperties } from 'react';
import MarkdownPreview from '@uiw/react-markdown-preview';
import { Button } from '@/components/ui/button';
import {
    Card,
    CardAction,
    CardContent,
    CardHeader,
    CardTitle,
} from '@/components/ui/card';
import {
    ContextMenu,
    ContextMenuContent,
    ContextMenuItem,
    ContextMenuTrigger,
} from '@/components/ui/context-menu';
import { translateText } from '@/lib/translation';

type LanguageKey = 'base' | 'target';

export type DualLanguageContent = {
    base?: string | null;
    target?: string | null;
};

type DualLanguageTextCardProps = {
    heading: string;
    content: DualLanguageContent | DualLanguageContent[] | null | undefined;
    emptyMessage?: string;
};

const markdownPreviewStyle = {
    backgroundColor: 'transparent',
    padding: 0,
    color: 'inherit',
    fontFamily: 'inherit',
    '--color-canvas-default': 'transparent',
    '--color-canvas-subtle': 'transparent',
} as CSSProperties;

const translationPreviewStyle = {
    backgroundColor: 'transparent',
    padding: 0,
    color: '#c2410c', // orange-700
    fontFamily: 'inherit',
    '--color-canvas-default': 'transparent',
    '--color-canvas-subtle': 'transparent',
} as CSSProperties;

const markdownPreviewClassName =
    'text-sm leading-6 text-slate-700 whitespace-pre-wrap [&>*]:m-0 [&>*:not(:last-child)]:mb-2';

const translationPreviewClassName =
    'text-xs leading-5 whitespace-pre-wrap [&>*]:m-0 [&>*:not(:last-child)]:mb-2 mt-2';

function getEntries(
    content: DualLanguageContent | DualLanguageContent[] | null | undefined,
): DualLanguageContent[] {
    if (!content) {
        return [];
    }

    return Array.isArray(content) ? content : [content];
}

function hasContent(entry: DualLanguageContent): boolean {
    return ['base', 'target'].some((key) => {
        const value = entry?.[key as LanguageKey];
        return typeof value === 'string' && value.trim().length > 0;
    });
}

function splitIntoParagraphs(text: string): string[] {
    // Split by double newlines and filter out empty paragraphs
    return text
        .split('\n\n')
        .map((p) => p.trim())
        .filter((p) => p.length > 0);
}

function canSplitIntoParagraphs(entry: DualLanguageContent): boolean {
    const targetText = entry?.target;
    const baseText = entry?.base;

    if (
        typeof targetText !== 'string' ||
        targetText.trim().length === 0 ||
        typeof baseText !== 'string' ||
        baseText.trim().length === 0
    ) {
        return false;
    }

    const targetParagraphs = splitIntoParagraphs(targetText);
    const baseParagraphs = splitIntoParagraphs(baseText);

    return targetParagraphs.length === baseParagraphs.length && targetParagraphs.length > 0;
}

function getEntryText(entry: DualLanguageContent, language: LanguageKey): string {
    const value = entry?.[language];
    if (typeof value === 'string' && value.trim().length > 0) {
        return value.trim();
    }

    const languageNames: Record<LanguageKey, string> = {
        base: 'English',
        target: 'German',
    };

    return `No ${languageNames[language]} content provided.`;
}

function renderEntryContent(entry: DualLanguageContent, showTranslation: boolean) {
    const canSplit = canSplitIntoParagraphs(entry);

    if (canSplit) {
        const targetText = entry.target?.trim() ?? '';
        const baseText = entry.base?.trim() ?? '';
        const targetParagraphs = splitIntoParagraphs(targetText);
        const baseParagraphs = splitIntoParagraphs(baseText);

        return (
            <div>
                {targetParagraphs.map((targetPara, index) => (
                    <div key={index} className="mb-4 last:mb-0">
                        <MarkdownPreview
                            className={markdownPreviewClassName}
                            source={targetPara}
                            style={markdownPreviewStyle}
                            wrapperElement={{ 'data-color-mode': 'light' }}
                        />
                        {showTranslation && (
                            <MarkdownPreview
                                className={translationPreviewClassName}
                                source={baseParagraphs[index]}
                                style={translationPreviewStyle}
                                wrapperElement={{ 'data-color-mode': 'light' }}
                            />
                        )}
                    </div>
                ))}
            </div>
        );
    } else {
        // Fallback: show Target by default, toggle to show base if needed
        console.warn(
            'Paragraph counts do not match for entry. Falling back to toggle behavior.',
        );
        const displayLanguage: LanguageKey = showTranslation ? 'base' : 'target';
        return (
            <MarkdownPreview
                className={markdownPreviewClassName}
                source={getEntryText(entry, displayLanguage)}
                style={markdownPreviewStyle}
                wrapperElement={{ 'data-color-mode': 'light' }}
            />
        );
    }
}

type TranslationPair = {
    original: string;
    translated: string;
};

export function DualLanguageTextCard({
    heading,
    content,
    emptyMessage = 'No content available.',
}: DualLanguageTextCardProps) {
    const [showTranslation, setShowTranslation] = useState<boolean>(false);
    const [highlightedText, setHighlightedText] = useState<string>('');
    const [translations, setTranslations] = useState<TranslationPair[]>([]);
    const [isTranslating, setIsTranslating] = useState<boolean>(false);
    const entries = getEntries(content);
    const hasAnyContent = entries.some(hasContent);

    const handleToggle = () => {
        setShowTranslation((prev) => !prev);
    };

    const handleContextMenu = () => {
        // Capture the highlighted text right before the custom menu opens.
        const text = window.getSelection()?.toString().trim() ?? '';
        setHighlightedText(text);
    };

    const handleTranslate = async () => {
        if (!highlightedText) return;

        // Check if this text is already translated
        const existingTranslation = translations.find(t => t.original === highlightedText);
        if (existingTranslation) {
            return; // Already translated, no need to translate again
        }

        setIsTranslating(true);
        try {
            const result = await translateText(highlightedText, 'en-US');
            // Add the new translation to the list
            setTranslations(prev => [...prev, {
                original: highlightedText,
                translated: result.text,
            }]);
        } catch (error) {
            console.error('Translation failed:', error);
            // Add error message to the list
            setTranslations(prev => [...prev, {
                original: highlightedText,
                translated: 'Translation failed. Please try again.',
            }]);
        } finally {
            setIsTranslating(false);
        }
    };

    const handleRemoveTranslation = (index: number) => {
        setTranslations(prev => prev.filter((_, i) => i !== index));
    };

    const handleClearAllTranslations = () => {
        setTranslations([]);
    };

    const handleAddToFlashcard = () => {
        console.log('Add to flash card:', highlightedText);
    };

    return (
        <div className="relative">
            <Card>
                <CardHeader>
                    <CardTitle className="text-lg font-semibold">{heading}</CardTitle>
                    <CardAction>
                        <div className="flex items-center gap-2">
                            <Button size="sm" variant="outline" onClick={handleToggle}>
                                {showTranslation ? 'Translate' : 'Translate'}
                            </Button>
                        </div>
                    </CardAction>
                </CardHeader>
                <CardContent>
                    <ContextMenu>
                        <ContextMenuTrigger asChild>
                            <div onContextMenu={handleContextMenu}>
                                {!hasAnyContent ? (
                                    <p className="text-sm text-muted-foreground">
                                        {emptyMessage}
                                    </p>
                                ) : (
                                    <div>
                                        {entries.map((entry, index) => (
                                            <div
                                                key={`${heading}-${index}`}
                                            >
                                                {renderEntryContent(entry, showTranslation)}
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </div>
                        </ContextMenuTrigger>
                        <ContextMenuContent>
                            <ContextMenuItem onSelect={handleTranslate} disabled={!highlightedText}>
                                Translate sentence
                            </ContextMenuItem>
                            <ContextMenuItem
                                onSelect={handleAddToFlashcard}
                                disabled={!highlightedText}
                            >
                                Add to flash card
                            </ContextMenuItem>
                        </ContextMenuContent>
                    </ContextMenu>
                </CardContent>
            </Card>

            {/* Translation Display - positioned next to the card */}
            {(translations.length > 0 || isTranslating) && (
                <div className="absolute left-full top-0 ml-4 max-w-sm w-80 bg-white border border-slate-200 rounded-lg shadow-lg p-4 z-50">
                    <div className="flex justify-between items-center mb-3">
                        <h3 className="text-sm font-semibold text-slate-900">Translations</h3>
                        <button
                            onClick={handleClearAllTranslations}
                            className="text-xs text-slate-500 hover:text-slate-700 transition-colors"
                            aria-label="Clear all translations"
                        >
                            Clear all
                        </button>
                    </div>
                    <div className="space-y-2 max-h-96 overflow-y-auto">
                        {translations.map((pair, index) => (
                            <div
                                key={index}
                                className="border border-slate-200 rounded-md p-2 hover:bg-slate-50 transition-colors group"
                            >
                                <div className="flex justify-between items-start gap-2">
                                    <div className="flex-1 min-w-0">
                                        <p className="text-xs text-slate-600 truncate">{pair.original}</p>
                                        <p className="text-sm text-slate-900 font-medium mt-0.5">
                                            {pair.translated}
                                        </p>
                                    </div>
                                    <button
                                        onClick={() => handleRemoveTranslation(index)}
                                        className="text-slate-400 hover:text-slate-600 transition-colors opacity-0 group-hover:opacity-100 flex-shrink-0"
                                        aria-label="Remove translation"
                                    >
                                        <svg
                                            xmlns="http://www.w3.org/2000/svg"
                                            width="14"
                                            height="14"
                                            viewBox="0 0 24 24"
                                            fill="none"
                                            stroke="currentColor"
                                            strokeWidth="2"
                                            strokeLinecap="round"
                                            strokeLinejoin="round"
                                        >
                                            <line x1="18" y1="6" x2="6" y2="18"></line>
                                            <line x1="6" y1="6" x2="18" y2="18"></line>
                                        </svg>
                                    </button>
                                </div>
                            </div>
                        ))}
                        {isTranslating && (
                            <div className="border border-slate-200 rounded-md p-2 bg-slate-50">
                                <div className="flex items-center gap-2">
                                    <div className="animate-spin rounded-full h-3 w-3 border-2 border-slate-300 border-t-slate-600"></div>
                                    <p className="text-xs text-slate-500">Translating...</p>
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
}
