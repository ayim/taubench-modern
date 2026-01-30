import { FC, useMemo, useState, useCallback, useEffect, useRef } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { Badge, Box, Button, Tabs, Typography } from '@sema4ai/components';
import { IconChevronDown, IconChevronRight } from '@sema4ai/icons';
import { ThreadMessage } from '@sema4ai/agent-server-interface';
import { Document, Page } from 'react-pdf';

import { Code } from '~/components/code';

import {
  threadMessagesQueryKey,
  useDownloadThreadFileMutation,
  useThreadMessageMetadataOpsMutation,
} from '~/queries/threads';
import { DocumentViewer } from '../../../DocIntel/shared/components/DocumentViewer';
import { useVioletChatContext } from '../../../context';

export type DocCard = {
  file_ref: string;
  file_id?: string;
  mime_type?: string;
  size_bytes?: number | null;
  status?: string;
  sampled_pages?: Array<{
    page?: number;
    status?: string;
    parse_data?: Record<string, unknown> | null;
    summary?: string | Record<string, unknown> | null;
    error?: string;
  }>;
  comments?: Array<{ comment: string; updated_at?: string | null; anchor?: Record<string, unknown> | null }>;
  json_schema?: Record<string, unknown> | null;
  updated_at?: string;
};

type NormalizedCard = {
  id: string;
  file_ref: string;
  status: string;
  mime_type?: string;
  size?: string;
  sampled_pages?: DocCard['sampled_pages'];
  updated_at?: string;
  json_schema?: Record<string, unknown> | null;
  comments?: DocCard['comments'];
};

type CommentAnchor = {
  x?: number;
  y?: number;
  normalized?: boolean;
  page?: number;
  field_id?: string;
};

type SelectPageHandler = (cardId: string, page: number) => void;
type MarkStatusHandler = (fileRef: string, status: string) => Promise<void>;
type FileLoader = (fileRef: string) => Promise<void>;
type SaveCommentHandler = (args: {
  fileRef: string;
  page: number;
  fieldId: string;
  text: string;
  anchor: { x: number; y: number; normalized?: boolean };
}) => Promise<void>;
type DeleteCommentHandler = (args: { fileRef: string; page: number; fieldId: string }) => Promise<void>;

const formatBytes = (bytes?: number) => {
  if (typeof bytes !== 'number' || Number.isNaN(bytes) || bytes < 0) return '';
  const kb = bytes / 1024;
  if (kb < 1024) return `${kb.toFixed(1)} KB`;
  const mb = kb / 1024;
  return `${mb.toFixed(1)} MB`;
};

const statusBadgeVariant = (status?: string): 'info' | 'success' | 'yellow' | 'red' | 'secondary' => {
  switch ((status || '').toLowerCase()) {
    case 'ready':
    case 'completed':
    case 'done':
    case 'parsed':
      return 'success';
    case 'parsing':
      return 'info';
    case 'sampling':
    case 'pending':
    case 'detected':
    case 'pending_markup':
    case 'in_progress':
      return 'secondary';
    case 'error':
      return 'red';
    default:
      return 'secondary';
  }
};

const findScrollParent = (node: HTMLElement | null): HTMLElement | null => {
  let current: HTMLElement | null = node;

  while (current) {
    const { overflowY, overflow } = window.getComputedStyle(current);
    const hasScroll = ['auto', 'scroll'].includes(overflowY) || ['auto', 'scroll'].includes(overflow);
    if (hasScroll && current.scrollHeight > current.clientHeight) {
      return current;
    }
    current = current.parentElement;
  }

  return (document.scrollingElement as HTMLElement | null) ?? null;
};

const DocCardItem: FC<{
  card: NormalizedCard;
  selected: { cardId: string; page: number } | null;
  onSelectPage: SelectPageHandler;
  fileCache: Record<string, File>;
  ensureFileLoaded: FileLoader;
  isDownloading: boolean;
  loadError: string | null;
  onMarkStatus: MarkStatusHandler;
  onSaveComment?: SaveCommentHandler;
  onDeleteComment?: DeleteCommentHandler;
}> = ({
  card,
  selected,
  onSelectPage,
  fileCache,
  ensureFileLoaded,
  isDownloading,
  loadError,
  onMarkStatus,
  onSaveComment,
  onDeleteComment,
}) => {
  const cardRef = useRef<HTMLDivElement | null>(null);
  const scrollParentRef = useRef<HTMLElement | null>(null);
  const [collapsed, setCollapsed] = useState(false);
  const [activeTab, setActiveTab] = useState(0);
  const selectedPage = selected && selected.cardId === card.id ? selected.page : card.sampled_pages?.[0]?.page;
  const selectedPageData = card.sampled_pages?.find((p) => p?.page === selectedPage);
  const pdfFile = fileCache[card.file_ref];

  useEffect(() => {
    // Auto-load the PDF so we can render page previews immediately.
    ensureFileLoaded(card.file_ref);
  }, [card.file_ref, ensureFileLoaded]);

  const normalizedParseData = useMemo(() => {
    const data = selectedPageData?.parse_data;
    if (!data || typeof data !== 'object') return null;
    return data as Record<string, unknown>;
  }, [selectedPageData?.parse_data]);

  const schemaString = useMemo(() => {
    if (!card.json_schema) return null;
    try {
      return JSON.stringify(card.json_schema, null, 2);
    } catch (err) {
      return null;
    }
  }, [card.json_schema]);

  const commentsByPage = useMemo(() => {
    const map: Record<
      number,
      Record<string, { text: string; anchor?: { x: number; y: number; normalized?: boolean } }>
    > = {};
    (card.comments || []).forEach((c, idx) => {
      const anchor = (c.anchor || {}) as CommentAnchor;
      const page =
        (anchor.page as number) || selectedPageData?.page || selectedPage || card.sampled_pages?.[0]?.page || 1;
      let fieldId = (anchor.field_id as string) || `comment-${idx}`;
      const existing = map[page]?.[fieldId];
      if (existing) {
        fieldId = `${fieldId}-${idx}`;
      }
      map[page] = map[page] || {};
      map[page][fieldId] = {
        text: c.comment,
        anchor:
          anchor.x != null && anchor.y != null
            ? { x: anchor.x as number, y: anchor.y as number, normalized: anchor.normalized as boolean | undefined }
            : undefined,
      };
    });
    return map;
  }, [card.comments, card.sampled_pages, selectedPage, selectedPageData?.page]);

  useEffect(() => {
    scrollParentRef.current = findScrollParent(cardRef.current);
  }, []);

  const handlePreviewClick = useCallback(
    (page?: number) => {
      if (!page || selectedPage === page) return;
      const container = scrollParentRef.current ?? findScrollParent(cardRef.current);
      const initialTop = cardRef.current?.getBoundingClientRect().top ?? null;
      const initialScrollTop = container?.scrollTop ?? null;

      onSelectPage(card.id, page);

      if (!container || initialTop === null) return;

      requestAnimationFrame(() => {
        if (!cardRef.current || !container) return;
        const newTop = cardRef.current.getBoundingClientRect().top;
        const delta = newTop - initialTop;

        if (Math.abs(delta) > 1) {
          container.scrollTop += delta;
        } else if (initialScrollTop !== null && container.scrollTop !== initialScrollTop) {
          container.scrollTop = initialScrollTop;
        }
      });
    },
    [card.id, onSelectPage, selectedPage],
  );

  const renderPreviewContent = () => {
    if (!selectedPageData) return null;

    let previewContent = (
      <Typography fontSize="$12" color="content.subtle">
        {selectedPageData.status === 'error' ? selectedPageData.error || 'Parsing failed' : 'Parsing in progress...'}
      </Typography>
    );

    if (normalizedParseData) {
      previewContent = pdfFile ? (
        <Box display="flex" flexDirection="column" style={{ minHeight: 400, height: '60vh', maxHeight: 560 }}>
          <DocumentViewer
            file={pdfFile}
            parseData={normalizedParseData}
            pageNumber={selectedPage ?? 1}
            commentsDisabled={card.status === 'done'}
            onCommentSave={(
              pageNumber: number,
              fieldId: string,
              text: string,
              anchor: { x: number; y: number; normalized?: boolean },
            ) => onSaveComment?.({ fileRef: card.file_ref, page: pageNumber, fieldId, text, anchor })}
            onCommentDelete={(pageNumber: number, fieldId: string) =>
              onDeleteComment?.({ fileRef: card.file_ref, page: pageNumber, fieldId })
            }
            commentsByPage={commentsByPage}
          />
        </Box>
      ) : (
        <Typography fontSize="$12" color="content.subtle">
          {isDownloading ? 'Loading PDF...' : 'Preparing preview...'}
        </Typography>
      );
    }

    return (
      <Box display="flex" flexDirection="column" gap="$6">
        <Typography fontSize="$12" color="content.subtle">
          Showing page {selectedPage}
        </Typography>
        {previewContent}
        {selectedPageData.summary && (
          <Typography fontSize="$12" color="content.subtle">
            Summary:{' '}
            {typeof selectedPageData.summary === 'string'
              ? selectedPageData.summary
              : JSON.stringify(selectedPageData.summary)}
          </Typography>
        )}
      </Box>
    );
  };

  const renderSchemaContent = () => {
    if (!card.json_schema) return null;

    return (
      <Box padding="$6" borderRadius="$6" display="flex" flexDirection="column" gap="$4">
        {schemaString ? (
          <Code lang="json" value={schemaString} readOnly lineNumbers rows={18} aria-label="Inferred schema JSON" />
        ) : (
          <Typography fontSize="$12" color="content.subtle">
            Unable to display schema.
          </Typography>
        )}
      </Box>
    );
  };

  const handleMarkDone = useCallback(async () => {
    await onMarkStatus(card.file_ref, 'done');
    setCollapsed(true);
  }, [card.file_ref, onMarkStatus]);

  return (
    <Box
      ref={cardRef}
      display="flex"
      flexDirection="column"
      gap="$8"
      padding="$8"
      borderRadius="$6"
      backgroundColor="background.primary"
    >
      <Box display="flex" alignItems="center" justifyContent="space-between" gap="$8">
        <Typography fontWeight="medium" color="content.primary">
          {card.file_ref}
        </Typography>
        <Box display="flex" alignItems="center" gap="$2">
          <Badge variant={statusBadgeVariant(card.status)} label={card.status} />
          {card.status !== 'done' ? (
            <Button size="small" variant="outline" onClick={handleMarkDone}>
              Mark done
            </Button>
          ) : (
            <Button size="small" variant="ghost" onClick={() => onMarkStatus(card.file_ref, 'pending_markup')}>
              Reopen
            </Button>
          )}
          <Button
            size="small"
            variant="ghost"
            round
            icon={collapsed ? IconChevronRight : IconChevronDown}
            aria-label={collapsed ? 'Expand document card' : 'Collapse document card'}
            onClick={() => setCollapsed((prev) => !prev)}
          />
        </Box>
      </Box>
      {/* <Typography fontSize="$12" color="content.subtle">
        {card.mime_type || 'PDF'} {card.size ? `• ${card.size}` : ''}
      </Typography> */}

      {!collapsed && card.sampled_pages && card.sampled_pages.length > 0 && (
        <Box
          display="flex"
          alignItems="stretch"
          gap="$4"
          padding="$2"
          flexWrap="nowrap"
          style={{
            maxWidth: '100%',
            paddingBottom: 12,
            overflowX: 'auto',
            overflowY: 'hidden',
            WebkitOverflowScrolling: 'touch',
            scrollbarWidth: 'thin',
          }}
        >
          {card.sampled_pages.map((p) => {
            const previewKey = p?.page != null ? `page-${p.page}` : `${card.id}-${p?.status ?? 'unknown-preview'}`;

            return (
              <button
                key={previewKey}
                style={{
                  position: 'relative',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '8px',
                  padding: '8px',
                  borderRadius: '6px',
                  cursor: p?.page ? 'pointer' : 'default',
                  flexShrink: 0,
                  minWidth: 120,
                  maxWidth: 150,
                  border:
                    selectedPage === p?.page
                      ? '2px solid var(--rc-color-border-emphasis, #3b82f6)'
                      : '1px solid var(--rc-color-border-subtle, #e5e7eb)',
                  boxShadow: selectedPage === p?.page ? '0 0 0 3px rgba(59,130,246,0.15)' : 'none',
                  background:
                    selectedPage === p?.page
                      ? 'var(--rc-color-surface, #fff)'
                      : 'var(--rc-color-surface-subtle, #f7f8fa)',
                }}
                type="button"
                onClick={() => handlePreviewClick(p?.page)}
              >
                <Badge
                  size="small"
                  variant={statusBadgeVariant(p?.status)}
                  label={`Page ${p?.page ?? '?'}`}
                  style={{ position: 'absolute', top: 6, left: 6, zIndex: 2 }}
                />
                {p?.status === 'parsing' && (
                  <div style={{ position: 'absolute', top: 6, right: 6, zIndex: 2 }}>
                    <svg width="18" height="18" viewBox="0 0 50 50" aria-label="Parsing page">
                      <circle
                        cx="25"
                        cy="25"
                        r="20"
                        stroke="#3b82f6"
                        strokeWidth="5"
                        fill="none"
                        strokeDasharray="31.4 188.4"
                      >
                        <animateTransform
                          attributeName="transform"
                          type="rotate"
                          from="0 25 25"
                          to="360 25 25"
                          dur="1s"
                          repeatCount="indefinite"
                        />
                      </circle>
                    </svg>
                  </div>
                )}
                {commentsByPage[p?.page ?? -1] && (
                  <Badge
                    size="small"
                    variant="info"
                    label={`${Object.keys(commentsByPage[p?.page ?? -1]).length} note${
                      Object.keys(commentsByPage[p?.page ?? -1]).length === 1 ? '' : 's'
                    }`}
                    style={{ position: 'absolute', bottom: 6, right: 6, zIndex: 2 }}
                  />
                )}
                {p?.page ? (
                  <Document
                    file={pdfFile || null}
                    loading={<Typography fontSize="$11">Loading…</Typography>}
                    error={
                      <Typography fontSize="$11" color="content.subtle">
                        {isDownloading ? 'Loading PDF…' : 'PDF not yet available'}
                      </Typography>
                    }
                  >
                    <Page
                      pageNumber={p.page}
                      width={120}
                      renderTextLayer={false}
                      renderAnnotationLayer={false}
                      loading={<Typography fontSize="$11">Loading…</Typography>}
                      error={<Typography fontSize="$11">Page unavailable</Typography>}
                    />
                  </Document>
                ) : (
                  <Typography fontSize="$11" color="content.subtle">
                    No page
                  </Typography>
                )}
              </button>
            );
          })}
        </Box>
      )}

      {!collapsed &&
        selectedPageData &&
        (card.json_schema ? (
          <Tabs display="flex" flexDirection="column" gap="$6" activeTab={activeTab} setActiveTab={setActiveTab}>
            <Tabs.Tab>Preview</Tabs.Tab>
            <Tabs.Tab>Inferred Schema</Tabs.Tab>
            <Tabs.Panel>{renderPreviewContent()}</Tabs.Panel>
            <Tabs.Panel>{renderSchemaContent()}</Tabs.Panel>
          </Tabs>
        ) : (
          renderPreviewContent()
        ))}

      {loadError && (
        <Typography fontSize="$12" color="content.error">
          {loadError}
        </Typography>
      )}
      {card.updated_at && (
        <Typography fontSize="$11" color="content.subtle">
          Updated {card.updated_at}
        </Typography>
      )}
    </Box>
  );
};

export const DocCards: FC<{ cards: DocCard[]; messageId: string }> = ({ cards, messageId }) => {
  const { threadId } = useVioletChatContext();
  const queryClient = useQueryClient();
  const { mutateAsync: downloadFileInline, isPending: isDownloading } = useDownloadThreadFileMutation({
    type: 'inline',
  });
  const { mutateAsync: applyMetadataOps } = useThreadMessageMetadataOpsMutation({});
  const [selected, setSelected] = useState<{ cardId: string; page: number } | null>(null);
  const [fileCache, setFileCache] = useState<Record<string, File>>({});
  const [loadError, setLoadError] = useState<string | null>(null);
  const [loadingFiles, setLoadingFiles] = useState<Record<string, boolean>>({});
  const [overrides, setOverrides] = useState<Record<string, Partial<NormalizedCard>>>({});

  const normalized: NormalizedCard[] = useMemo(
    () =>
      cards.map((c) => ({
        id: c.file_ref || c.file_id || String(Math.random()),
        file_ref: c.file_ref || c.file_id || 'Unknown file',
        status: c.status || 'pending',
        mime_type: c.mime_type,
        size: formatBytes(c.size_bytes ?? undefined),
        sampled_pages: c.sampled_pages,
        updated_at: c.updated_at,
        json_schema: c.json_schema,
        comments: c.comments,
      })),
    [cards],
  );

  const mergedCards: NormalizedCard[] = useMemo(
    () =>
      normalized.map((c) => {
        const override = overrides[c.file_ref];
        if (!override) return c;
        return {
          ...c,
          ...override,
          sampled_pages: override.sampled_pages ?? c.sampled_pages,
          comments: override.comments ?? c.comments,
        };
      }),
    [normalized, overrides],
  );

  const ensureFileLoaded = useCallback(
    async (fileRef: string) => {
      if (!threadId || fileCache[fileRef] || loadingFiles[fileRef]) return;
      setLoadingFiles((prev) => ({ ...prev, [fileRef]: true }));
      setLoadError(null);
      try {
        const res = await downloadFileInline({ threadId, name: fileRef });
        if (res && 'file' in res && res.file instanceof File) {
          setFileCache((prev) => ({ ...prev, [fileRef]: res.file }));
        }
      } catch (err) {
        setLoadError(err instanceof Error ? err.message : 'Failed to load PDF');
      } finally {
        setLoadingFiles((prev) => ({ ...prev, [fileRef]: false }));
      }
    },
    [downloadFileInline, fileCache, loadingFiles, threadId],
  );

  const handleSelectPage = useCallback((cardId: string, page: number) => {
    setSelected({ cardId, page });
  }, []);

  const handleMarkStatus = useCallback(
    async (fileRef: string, status: string) => {
      if (!threadId) return;
      const res = await applyMetadataOps({
        threadId,
        messageId,
        ops: [{ op: 'doc_int/set_status', file_ref: fileRef, status }],
      });
      setOverrides((prev) => ({
        ...prev,
        [fileRef]: { ...(prev[fileRef] || {}), status },
      }));
      if (res) {
        queryClient.setQueryData(threadMessagesQueryKey(threadId), (existing: ThreadMessage[] | undefined) => {
          if (!Array.isArray(existing)) return existing;
          return existing.map((msg) => {
            if (msg.message_id !== messageId) return msg;
            const agentMeta = { ...(msg.agent_metadata || {}) };
            if (res.doc_cards) agentMeta.doc_cards = res.doc_cards;
            if (res.doc_int_revision !== undefined) agentMeta.doc_int_revision = res.doc_int_revision;
            if (res.doc_int_input_locked !== undefined) agentMeta.doc_int_input_locked = res.doc_int_input_locked;
            if (res.doc_int) agentMeta.doc_int = res.doc_int;
            return { ...msg, agent_metadata: agentMeta };
          });
        });
      }
    },
    [applyMetadataOps, messageId, queryClient, threadId],
  );

  const handleSaveComment = useCallback(
    async ({
      fileRef,
      page,
      fieldId,
      text,
      anchor,
    }: {
      fileRef: string;
      page: number;
      fieldId: string;
      text: string;
      anchor: { x: number; y: number; normalized?: boolean };
    }) => {
      if (!threadId) return;
      const trimmed = text.trim();
      await applyMetadataOps({
        threadId,
        messageId,
        ops: [
          {
            op: 'doc_int/add_comment',
            file_ref: fileRef,
            comment: trimmed,
            page,
            anchor: { ...anchor, page, field_id: fieldId },
          },
        ],
      });
      setOverrides((prev) => {
        const baseComments = prev[fileRef]?.comments || mergedCards.find((c) => c.file_ref === fileRef)?.comments || [];
        return {
          ...prev,
          [fileRef]: {
            ...(prev[fileRef] || {}),
            comments: [
              ...baseComments,
              {
                comment: trimmed,
                updated_at: new Date().toISOString(),
                anchor: { ...anchor, page, field_id: fieldId },
              },
            ],
          },
        };
      });
    },
    [applyMetadataOps, mergedCards, threadId],
  );

  return (
    <Box
      display="flex"
      flexDirection="column"
      gap="$8"
      padding="$12"
      borderRadius="$8"
      borderColor="border.subtle"
      borderWidth="1px"
      backgroundColor="background.primary"
      marginTop="$8"
    >
      <Typography fontWeight="bold" fontSize="$14" color="content.primary">
        Documents
      </Typography>
      <Box display="flex" flexDirection="column" gap="$12">
        {mergedCards.map((card) => (
          <DocCardItem
            key={card.id}
            card={card}
            selected={selected}
            onSelectPage={handleSelectPage}
            fileCache={fileCache}
            ensureFileLoaded={ensureFileLoaded}
            isDownloading={isDownloading || loadingFiles[card.file_ref]}
            loadError={loadError}
            onMarkStatus={handleMarkStatus}
            onSaveComment={handleSaveComment}
            onDeleteComment={async (args) => {
              if (!threadId) return;
              await applyMetadataOps({
                threadId,
                messageId,
                ops: [{ op: 'doc_int/delete_comment', file_ref: args.fileRef, field_id: args.fieldId }],
              });
              setOverrides((prev) => {
                const baseComments =
                  prev[args.fileRef]?.comments || mergedCards.find((c) => c.file_ref === args.fileRef)?.comments || [];
                const filtered = baseComments.filter((c) => !(c.anchor && c.anchor.field_id === args.fieldId));
                return {
                  ...prev,
                  [args.fileRef]: { ...(prev[args.fileRef] || {}), comments: filtered },
                };
              });
            }}
          />
        ))}
      </Box>
    </Box>
  );
};
