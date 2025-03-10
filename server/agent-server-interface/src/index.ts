export * from "./schema";
export * from "./spec.gen";

import * as publicSchema from "./public-schema";
import * as publicSpec from "./public-spec.gen";

export const publicApi = {
  ...publicSchema,
  ...publicSpec,
};
