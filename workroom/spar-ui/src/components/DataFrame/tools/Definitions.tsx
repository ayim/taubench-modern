import { ThreadToolUsageContent } from '@sema4ai/agent-server-interface';
import { DataFrameCallbackDataFrameCreation, DataFrameCallbackState } from './Tools';

export const DATA_FRAME_TOOL_PREFIX = 'data_frames_';

/**
 * Corresponding server tool calls that we are listening to that require specific client action - eg. data refetch
 */
const SERVER_TOOLS_THAT_REQUIRE_CLIENT_ACTION = {
  CREATE_FROM_FILE: `${DATA_FRAME_TOOL_PREFIX}create_from_file`,
  CREATE_FROM_SQL: `${DATA_FRAME_TOOL_PREFIX}create_from_sql`,
};

export class DataFrameClientTools {
  /**
   * Client tool definitions for Data Frame interactive components
   * These tools provide user interaction points during data frame creation workflows
   */

  static chooseToolToRender = (tool: ThreadToolUsageContent, state: DataFrameCallbackState) => {
    switch (tool.name) {
      case SERVER_TOOLS_THAT_REQUIRE_CLIENT_ACTION.CREATE_FROM_FILE:
      case SERVER_TOOLS_THAT_REQUIRE_CLIENT_ACTION.CREATE_FROM_SQL:
        return <DataFrameCallbackDataFrameCreation key={`${tool.content_id}-callback`} state={state} />;
      default:
        return null;
    }
  };

  /**
   * Export all client tools for Data Frames
   */
  static clientToolsList = [];
}
