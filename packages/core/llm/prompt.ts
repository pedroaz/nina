


export interface PromptInput {

}

function role(): string {
    return `Your Role: You are a helpful german teacher.`;
}

function textLanguage(): string {
    return `The lesson must be written in english and german.`;
}

function objective(topic: string): string {
    return `Your objective is to write a lesson about ${topic}.`;
}

function vocabularyToConsider(vocabulary: string): string {
    return `Include the following vocabulary when creating exercises and examples in the lesson: ${vocabulary}.`;
}

function titleInstruction(): string {
    return `Create a concise and engaging title for the lesson.`;
}

function quickSummaryInstruction(): string {
    return `Provide a brief summary of the lesson, highlighting the key points that will be covered.`;
}

function quickExamplesInstruction(): string {
    return `Provide 3 quick examples that illustrate the topic. Each example should be brief and to the point.`;
}

function fullExplanationInstruction(): string {
    return `Provide a comprehensive explanation of the topic, covering all essential aspects in detail. Make it maximum 3 paragraphs.`;
}


export function createFinalPrompt(topic: string, vocabulary: string): string {
    const final = `
    ${role()}\n
    ${textLanguage()}\n
    ${objective(topic)}\n
    ${vocabularyToConsider(vocabulary)}\n
    ${titleInstruction()}\n
    ${quickSummaryInstruction()}\n
    ${quickExamplesInstruction()}\n
    ${fullExplanationInstruction()}\n
`;

    return final.trim();
}