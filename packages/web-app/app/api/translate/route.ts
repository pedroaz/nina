import { NextRequest, NextResponse } from 'next/server';
import * as deepl from 'deepl-node';

const authKey = process.env.DEEPL_API_KEY;

if (!authKey) {
    throw new Error('DEEPL_API_KEY is not set in environment variables');
}

const deeplClient = new deepl.Translator(authKey);

export async function POST(request: NextRequest) {
    try {
        const { text, targetLang = 'en-US', sourceLang } = await request.json();

        if (!text || typeof text !== 'string') {
            return NextResponse.json(
                { error: 'Text is required and must be a string' },
                { status: 400 },
            );
        }

        const result = await deeplClient.translateText(
            text,
            sourceLang || null,
            targetLang as deepl.TargetLanguageCode,
        );

        return NextResponse.json({
            text: result.text,
            detectedSourceLang: result.detectedSourceLang,
        });
    } catch (error) {
        console.error('Translation error:', error);
        return NextResponse.json(
            { error: 'Failed to translate text' },
            { status: 500 },
        );
    }
}
