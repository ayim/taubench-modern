import { ManagedIdentityCredential } from '@azure/identity';
import { BlobServiceClient, ContainerClient } from '@azure/storage-blob';
import type { Result } from '../../utils/result.js';

export type AzureContainerClientResult = Result<{
  blobServiceClient: BlobServiceClient;
  containerClient: ContainerClient;
}>;

/**
 * Fetch Azure clients that are implicitly authenticated using the
 * container environment provided by the platform. They require the
 * client ID from the UAI.
 * @see {@link https://learn.microsoft.com/en-us/javascript/api/@azure/identity/managedidentitycredential?view=azure-node-latest|Azure ManagedIdentityCredential docs}
 */
export const getImplicitlyAuthenticatedClients = async ({
  clientId,
  container,
  endpoint,
}: {
  clientId: string;
  container: string;
  endpoint: string;
}): Promise<AzureContainerClientResult> => {
  const credential = new ManagedIdentityCredential({ clientId });
  const blobServiceClient = new BlobServiceClient(endpoint, credential);

  const containerClient = blobServiceClient.getContainerClient(container);

  return {
    success: true,
    data: {
      blobServiceClient,
      containerClient,
    },
  };
};
