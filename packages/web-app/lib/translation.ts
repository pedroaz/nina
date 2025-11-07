export type TranslationResult = {
    text: string;
    detectedSourceLang?: string;
};

export async function translateText(
    text: string,
    targetLang: string = 'en-US',
    sourceLang?: string,
): Promise<TranslationResult> {
    try {
        const response = await fetch('/api/translate', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                text,
                targetLang,
                sourceLang,
            }),
        });

        if (!response.ok) {
            throw new Error('Translation request failed');
        }

        const result = await response.json();
        return result;
    } catch (error) {
        console.error('Translation error:', error);
        throw new Error('Failed to translate text');
    }
}
