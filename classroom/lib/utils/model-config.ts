import { useSettingsStore } from '@/lib/store/settings';
import {
  getThinkingConfigKey,
  normalizeThinkingConfig,
  supportsConfigurableThinking,
} from '@/lib/ai/thinking-config';
import { findModelById } from '@/lib/ai/model-aliases';
import { getCatalogThinkingCapability } from '@/lib/ai/model-metadata';

import type { ProviderId } from '@/lib/types/provider';

/**
 * Get current model configuration from settings store
 */
export function getCurrentModelConfig() {
  let { providerId, modelId, providersConfig, thinkingConfigs } = useSettingsStore.getState();

  // Self-heal: if modelId or providerId is empty or not configured, auto-select from server or usable providers
  if (!modelId || !providerId || !providersConfig[providerId]) {
    // 1. Check for server-configured provider with models
    const serverProvider = Object.entries(providersConfig).find(
      ([, cfg]) => cfg.isServerConfigured && cfg.models && cfg.models.length > 0,
    );
    // 2. Or check for provider with apiKey or not requiring apiKey with models
    const usableProvider = serverProvider || Object.entries(providersConfig).find(
      ([, cfg]) => (cfg.apiKey || !cfg.requiresApiKey) && cfg.models && cfg.models.length > 0,
    );

    if (usableProvider) {
      providerId = usableProvider[0] as ProviderId;
      modelId = usableProvider[1].models[0]?.id || '';
      // Update store state so subsequent calls and UI stay in sync
      useSettingsStore.setState({
        providerId,
        modelId,
      });
    }
  }

  const modelString = `${providerId}:${modelId}`;

  // Get current provider's config
  const providerConfig = providersConfig[providerId];
  const modelInfo = findModelById(providerId, providerConfig?.models, modelId);
  const thinking =
    modelInfo?.capabilities?.thinking ?? getCatalogThinkingCapability(providerId, modelId);
  const thinkingConfig = supportsConfigurableThinking(thinking)
    ? normalizeThinkingConfig(thinking, thinkingConfigs[getThinkingConfigKey(providerId, modelId)])
    : undefined;

  return {
    providerId,
    modelId,
    modelString,
    apiKey: providerConfig?.apiKey || '',
    baseUrl: providerConfig?.baseUrl || '',
    providerType: providerConfig?.type,
    requiresApiKey: providerConfig?.requiresApiKey,
    isServerConfigured: providerConfig?.isServerConfigured,
    thinkingConfig,
  };
}
