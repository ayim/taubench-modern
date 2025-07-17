const dateTimeFormatter = new Intl.DateTimeFormat('en-US', {
  year: 'numeric',
  month: 'long',
  day: 'numeric',
  hour: 'numeric',
  minute: 'numeric',
  hour12: true,
});

export const formatDatetime = (date?: Date | string | null): string | undefined => {
  if (!date) return undefined;
  const result = dateTimeFormatter.format(new Date(date));
  return result;
};
