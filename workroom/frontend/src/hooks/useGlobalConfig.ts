import { useConfigQuery } from '~/queries/settings';

export enum GlobalConfigType {
  defaultLLMPlatformId = 'DEFAULT_LLM_PLATFORM_PARAMS_ID',
}

export const useGlobalConfig = (configType: GlobalConfigType) => {
  const { data } = useConfigQuery({});

  switch (configType) {
    case GlobalConfigType.defaultLLMPlatformId:
      return data?.find((c) => c.config_type === 'DEFAULT_LLM_PLATFORM_PARAMS_ID')?.config_value;
    default:
      return undefined;
  }
};
