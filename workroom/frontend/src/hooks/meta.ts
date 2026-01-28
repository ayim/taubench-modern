import { useEffect, useState } from 'react';
import { getMeta, Meta } from '~/lib/meta';

export const useMeta = (): Meta | null => {
  const [meta, setMeta] = useState<Meta | null>(null);

  useEffect(() => {
    getMeta()
      .then((newMeta) => setMeta(newMeta))
      .catch((err) => {
        // eslint-disable-next-line no-console
        console.error('Failed retrieving meta', err);
      });
  }, []);

  return meta;
};
