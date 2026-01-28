export const URL_REGEX =
  /((https?:\/\/(www\.)?)|(www\.))[-a-zA-Z0-9@:%._+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b([-a-zA-Z0-9()@:%_+.~#?&//=]*)(?<![-.+():%])/;

export const EMAIL_REGEX =
  /(([^<>()[\]\\.,;:\s@"]+(\.[^<>()[\]\\.,;:\s@"]+)*)|(".+"))@((\[[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\])|(([a-zA-Z\-0-9]+\.)+[a-zA-Z]{2,}))/;

const SUPPORTED_URL_PROTOCOLS = new Set(['http:', 'https:', 'mailto:', 'sms:', 'tel:']);

export const sanitizeUrl = (url: string): string => {
  try {
    const parsedUrl = new URL(url);
    // eslint-disable-next-line no-script-url
    if (!SUPPORTED_URL_PROTOCOLS.has(parsedUrl.protocol)) {
      return 'about:blank';
    }
  } catch {
    return url;
  }
  return url;
};

// Source: https://stackoverflow.com/a/8234912/2013580
export const validateUrl = (url: string, hasDomain?: boolean): boolean => {
  const urlRegExp =
    /((([A-Za-z]{3,9}:(?:\/\/)?)(?:[-;:&=+$,\w]+@)?[A-Za-z0-9.-]+|(?:www.|[-;:&=+$,\w]+@)[A-Za-z0-9.-]+)((?:\/[+~%/.\w-_]*)?\??(?:[-+=&;%@.\w_]*)#?(?:[\w]*))?)/;
  // TODO Fix UI for link insertion; it should never default to an invalid URL such as https://.
  // Maybe show a dialog where they user can type the URL before inserting it.
  const urlWithDomainRegExp = /^(https?:\/\/)?(www\.)?([a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}(\/[\w-]*)*\/?$/;

  return !hasDomain ? url === 'https://' || urlRegExp.test(url) : urlWithDomainRegExp.test(url);
};
