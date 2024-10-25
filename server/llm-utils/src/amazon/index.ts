import {
  BedrockRuntimeClient,
  BedrockRuntimeServiceException,
  InvokeModelCommand,
} from '@aws-sdk/client-bedrock-runtime';
import { TestLLMConfigurationResponse } from '../types';
import { AmazonLLMConfiguration } from './types';

export const testAmazonConfiguration = async (
  configuration: AmazonLLMConfiguration,
): Promise<TestLLMConfigurationResponse> => {
  const {
    model,
    config: { aws_secret_access_key, aws_access_key_id, region_name },
  } = configuration;

  if (!model || !aws_access_key_id || !aws_secret_access_key || !region_name) {
    const missingFields = [];
    if (!model) missingFields.push('model');
    if (!aws_access_key_id) missingFields.push('aws_access_key_id');
    if (!aws_secret_access_key) missingFields.push('aws_secret_access_key');
    if (!region_name) missingFields.push('region_name');
    return {
      success: false,
      error: {
        code: 'LLM_CONFIG_VALIDATION_ERROR',
        message: 'Validation error, missing fields',
        fields: missingFields,
      },
    };
  }

  const client = new BedrockRuntimeClient({
    region: region_name,
    credentials: {
      accessKeyId: aws_access_key_id,
      secretAccessKey: aws_secret_access_key,
    },
  });

  const command = new InvokeModelCommand({
    modelId: model,
    contentType: 'application/json',
    accept: 'application/json',
    body: JSON.stringify({
      messages: [{ role: 'user', content: 'Just testing.' }],
      max_tokens: 300,
      anthropic_version: 'bedrock-2023-05-31',
    }),
  });

  try {
    const response = await client.send(command);
    if (!response.body) {
      return {
        success: false,
        error: {
          code: 'INVALID_LLM_CONFIG',
          message: 'Failed to validate LLM, the response body was empty',
          fields: [],
        },
      };
    }
    return { success: true, data: {} };
  } catch (error) {
    if (error instanceof BedrockRuntimeServiceException) {
      if (error.name === 'UnrecognizedClientException') {
        return {
          success: false,
          error: {
            code: 'INVALID_LLM_CONFIG',
            message: 'Invalid AWS access key ID',
            fields: ['aws_access_key_id'],
          },
        };
      } else if (error.name === 'InvalidSignatureException') {
        return {
          success: false,
          error: {
            code: 'INVALID_LLM_CONFIG',
            message: 'Invalid AWS secret access key',
            fields: ['aws_secret_access_key'],
          },
        };
      }
    }
    if ((error as { code: string })?.code === 'ENOTFOUND') {
      return {
        success: false,
        error: {
          code: 'INVALID_LLM_CONFIG',
          message: 'Invalid AWS region',
          fields: ['region_name'],
        },
      };
    }
    return {
      success: false,
      error: {
        code: 'INVALID_LLM_CONFIG',
        message: 'Unexpected error',
        fields: [],
      },
    };
  }
};
