import { FC } from 'react';
import {
  IconAnyModel,
  IconConfluence,
  IconMsSQL,
  IconMySQL,
  IconOracle,
  IconPostgresql,
  IconRedshift,
  IconSalesforce,
  IconSlack,
  IconSnowflake,
  IconTimescale,
  IconKnowledgeBase,
} from '@sema4ai/icons/logos';
import { IconDatabase, IconProps, IconType } from '@sema4ai/icons';

type Props = IconProps & {
  engine: string;
};

export const getDataConnectionIcon = (engine: string): IconType => {
  switch (engine) {
    case 'postgres':
      return IconPostgresql;
    case 'pgvector':
      return IconPostgresql;
    case 'snowflake':
      return IconSnowflake;
    case 'redshift':
      return IconRedshift;
    case 'slack':
      return IconSlack;
    case 'mysql':
      return IconMySQL;
    case 'mssql':
      return IconMsSQL;
    case 'oracle':
      return IconOracle;
    case 'confluence':
      return IconConfluence;
    case 'salesforce':
      return IconSalesforce;
    case 'timescaledb':
      return IconTimescale;
    case 'custom':
      return IconAnyModel;
    case 'sema4_knowledge_base':
      return IconKnowledgeBase;
    default:
      return IconDatabase;
  }
};

export const DataConnectionIcon: FC<Props> = ({ engine, ...rest }) => {
  const Icon = getDataConnectionIcon(engine);
  return <Icon {...rest} />;
};
