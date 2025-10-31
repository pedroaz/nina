


export interface PromptInput {

}

function role(): string {
    return `You are a helpful german teacher.`;
}

function textLanguage(): string {
    return `The lesson must be written in english and german.`;
}

function action(userInput: string): string {
    return `Create a german lesson based on the following user input: ${userInput}`;
}

export function createFinalPrompt(input: string): string {
    const roleText = role();
    const actionText = action(input);

    return `${roleText}\n\n${actionText}`;
}