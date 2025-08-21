export const getBasePath = (): string => {
  const baseElement = document.head.querySelector('base');

  return new URL(baseElement!.href).pathname;
};
