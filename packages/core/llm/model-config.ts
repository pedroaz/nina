/**
 * Model Configuration
 *
 * Defines different model categories and their configurations.
 * This allows for easy switching between models and provides
 * metadata for user feedback.
 */

export const MODEL_CATEGORIES = {
    DETAILED: 'detailed',
    FAST: 'fast',
} as const;

export type ModelCategory = typeof MODEL_CATEGORIES[keyof typeof MODEL_CATEGORIES];

export interface ModelConfig {
    name: string;
    displayName: string;
    description: string;
    useCase: string;
}

export const MODEL_CONFIG: Record<ModelCategory, ModelConfig> = {
    detailed: {
        name: 'gpt-5-nano',
        displayName: 'Detailed Model (GPT-5 Nano)',
        description: 'More thorough and detailed responses, optimized for complex educational content',
        useCase: 'lesson creation',
    },
    fast: {
        name: 'gpt-4o-mini',
        displayName: 'Fast Model (GPT-4o Mini)',
        description: 'Quick and efficient responses, optimized for real-time interaction',
        useCase: 'chat',
    },
} as const;

/**
 * Get model configuration by category
 */
export function getModelConfig(category: ModelCategory): ModelConfig {
    return MODEL_CONFIG[category];
}

/**
 * Get model name by category
 */
export function getModelName(category: ModelCategory): string {
    return MODEL_CONFIG[category].name;
}
