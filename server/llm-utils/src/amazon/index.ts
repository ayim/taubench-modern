import {
  BedrockRuntimeClient,
  BedrockRuntimeServiceException,
  InvokeModelCommand,
} from '@aws-sdk/client-bedrock-runtime';
import { TestLLMConfigurationResponse } from '../types';
import { AmazonLLMConfiguration } from './types';
import { validateRequiredFields } from '../utils/validation';

export const testAmazonConfiguration = async (
  configuration: AmazonLLMConfiguration,
): Promise<TestLLMConfigurationResponse> => {
  const {
    model,
    config: { aws_secret_access_key, aws_access_key_id, region_name },
  } = configuration;

  const missingFields = validateRequiredFields([
    { value: model, fieldName: 'model' },
    { value: aws_access_key_id, fieldName: 'aws_access_key_id' },
    { value: aws_secret_access_key, fieldName: 'aws_secret_access_key' },
    { value: region_name, fieldName: 'region_name' },
  ]);

  if (missingFields) {
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
