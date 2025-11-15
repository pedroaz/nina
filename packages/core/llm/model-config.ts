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

/**
 * Model Pricing Configuration
 * Prices are in USD per token
 */
export const MODEL_PRICING = {
    'gpt-5-nano': {
        input: 0.050 / 1_000_000,      // $0.050 per 1M tokens
        cachedInput: 0.005 / 1_000_000, // $0.005 per 1M tokens (not currently tracked)
        output: 0.400 / 1_000_000       // $0.400 per 1M tokens
    },
    'gpt-4o-mini': {
        input: 0.15 / 1_000_000,        // $0.15 per 1M tokens
        cachedInput: 0.075 / 1_000_000, // $0.075 per 1M tokens (not currently tracked)
        output: 0.60 / 1_000_000        // $0.60 per 1M tokens
    },
} as const;

export type ModelName = keyof typeof MODEL_PRICING;

export interface CostBreakdown {
    inputCost: number;
    outputCost: number;
    totalCost: number;
}

/**
 * Calculate cost based on token usage
 * @param modelName - The model used (e.g., 'gpt-5-nano', 'gpt-4o-mini')
 * @param inputTokens - Number of input tokens
 * @param outputTokens - Number of output tokens
 * @returns Cost breakdown in USD
 */
export function calculateCost(
    modelName: ModelName,
    inputTokens: number,
    outputTokens: number
): CostBreakdown {
    const pricing = MODEL_PRICING[modelName];

    if (!pricing) {
        console.warn(`Unknown model: ${modelName}. Returning zero cost.`);
        return { inputCost: 0, outputCost: 0, totalCost: 0 };
    }

    const inputCost = inputTokens * pricing.input;
    const outputCost = outputTokens * pricing.output;
    const totalCost = inputCost + outputCost;

    return {
        inputCost: Number(inputCost.toFixed(6)),
        outputCost: Number(outputCost.toFixed(6)),
        totalCost: Number(totalCost.toFixed(6)),
    };
}
