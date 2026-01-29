import { ComponentProps } from 'react';

import { QueryError, ResourceType } from '~/queries/shared';
import { Illustration } from '../components/Illustration';

type ErrorDetails = Exclude<QueryError['details'], undefined>;

type ErrorType = Exclude<ErrorDetails['type'], undefined>;
type ErrorCode = Exclude<ErrorDetails['code'], undefined>;

type IllustrationName = ComponentProps<typeof Illustration>['name'];

type ErrorDescription = { title: string; description: string; type: ErrorType };
const GENERIC_RESPONSE: ErrorDescription = {
  title: "Something didn't go as expected",
  description: 'There was an issue processing your request. Please try again later.',
  type: 'error',
};

const ERROR_CODE_DETAILS: Record<ErrorCode, ErrorDescription> = {
  not_found: {
    title: 'Not Found',
    description: 'The content you are looking for is not there.',
    type: 'notice',
  },
  unauthorized: {
    title: 'Authentication Required',
    description: 'You need to be logged in to view this page.',
    type: 'notice',
  },
  forbidden: {
    title: 'Access Denied',
    description: 'Missing access to view this content.',
    type: 'error',
  },
  too_many_requests: {
    title: GENERIC_RESPONSE.title,
    description: 'There was a connection issue. Please try again later.',
    type: 'error',
  },
  method_not_allowed: {
    title: GENERIC_RESPONSE.title,
    description: 'There was a connection issue. Please try again later.',
    type: 'error',
  },
  conflict: GENERIC_RESPONSE,
  bad_request: GENERIC_RESPONSE,
  unexpected: GENERIC_RESPONSE,
  precondition_failed: GENERIC_RESPONSE,
  unprocessable_entity: GENERIC_RESPONSE,
};

const RESOURCE_TYPE_TITLE: Record<ResourceType, string> = {
  agent: 'Agent',
  data_connection: 'Data Connection',
  data_frame: 'Data Frame',
  document_intelligence: 'Document Intelligence',
  eval: 'Evaluation',
  feedback: 'Feedback',
  mcp_server: 'MCP Server',
  semantic_data: 'Semantic Data',
  thread: 'Conversation',
  thread_file: 'File',
  work_item: 'Work Item',
  integration: 'Integration',
  llm_platform: 'LLM Platform',
};

const ILLUSTRATION_NAME: Record<ResourceType, IllustrationName> = {
  agent: 'agents',
  data_connection: 'generic',
  data_frame: 'generic',
  document_intelligence: 'generic',
  eval: 'generic',
  feedback: 'generic',
  mcp_server: 'generic',
  semantic_data: 'generic',
  thread: 'agents',
  thread_file: 'generic',
  work_item: 'generic',
  integration: 'generic',
  llm_platform: 'generic',
};

type ResourceDetails = { type?: ResourceType; title?: string; illustration: IllustrationName };
const getResourceDetails = (resourceType?: ResourceType): ResourceDetails => {
  if (typeof resourceType === 'string' && resourceType in RESOURCE_TYPE_TITLE) {
    return {
      type: resourceType,
      title: RESOURCE_TYPE_TITLE[resourceType],
      illustration: ILLUSTRATION_NAME[resourceType],
    };
  }

  return {
    type: resourceType,
    title: undefined,
    illustration: 'generic',
  };
};

export const getParsedQueryError = (
  error?: QueryError | null,
): ErrorDescription & { message?: string; resource: ResourceDetails } => {
  const errorDetails = error?.details;

  const errorMessage = error?.message;
  const errorType = errorDetails?.type;
  const errorCode = errorDetails?.code as string | undefined;
  const resourceDetails = getResourceDetails(errorDetails?.resource);

  if (errorCode === 'not_found' && typeof resourceDetails.title === 'string') {
    return {
      title: `${resourceDetails.title} not found`,
      description: `The ${resourceDetails.title.toLowerCase()} you are looking for was not found.`,
      type: errorType ?? ERROR_CODE_DETAILS[errorCode].type,
      resource: resourceDetails,
    };
  }

  const errorDescription =
    typeof errorCode === 'string' && errorCode in ERROR_CODE_DETAILS
      ? ERROR_CODE_DETAILS[errorCode as ErrorCode]
      : GENERIC_RESPONSE;

  return {
    ...errorDescription,
    type: errorType ?? errorDescription.type,
    message: errorMessage,
    resource: resourceDetails,
  };
};
