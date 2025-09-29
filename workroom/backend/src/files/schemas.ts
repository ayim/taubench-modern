import z from 'zod';

export const DeleteFileBody = z.object({
  fileId: z.string(),
});

export const GetDownloadUrlQuery = z.object({
  fileId: z.string(),
  fileName: z.string(),
  expiresIn: z.coerce.number(),
});

export const GetPostSignedUrlBody = z.object({
  fileId: z.string(),
  expiresIn: z.number(),
  fileSize: z.number().optional(),
  fileType: z.string().optional(),
});
