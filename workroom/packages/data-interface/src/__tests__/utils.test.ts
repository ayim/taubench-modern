import { describe, expect, it } from 'vitest';
import { customerFacingDataSourceEngineName } from '../lib/utils';
import type { DataSourceEngine } from '../lib/dataSources';

describe.each([
  ['postgres', 'PostgreSQL'] satisfies [DataSourceEngine, string],
  ['prediction:lightwood', 'Lightwood Predictions'] satisfies [DataSourceEngine, string],
  ['redshift', 'Redshift'] satisfies [DataSourceEngine, string],
  ['databricks', 'Databricks'] satisfies [DataSourceEngine, string],
  ['unknown', 'Unknown'] satisfies [unknown, string],
  [[], 'Unknown'] satisfies [unknown, string],
  [{}, 'Unknown'] satisfies [unknown, string],
  [undefined, 'Unknown'] satisfies [unknown, string],
  [null, 'Unknown'] satisfies [unknown, string],
  [false, 'Unknown'] satisfies [unknown, string],
])('customerFacingDataSourceEngineName', (input, expected) => {
  it(`should transform ${input} to ${expected}`, () => {
    expect(customerFacingDataSourceEngineName(input as DataSourceEngine)).toBe(expected);
  });
});
