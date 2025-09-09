import { createTool } from '@sema4ai/sai-sdk';
import { ThreadToolUsageContent } from '@sema4ai/agent-server-interface';
import { DataFrameCallbackDataFrameCreation, DataFrameConfirmParseDataFrameFile } from './Tools';

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

  /**
   * Show confirmation actions for the user to confirm the data frame creation from file.
   */
  static askUserToConfirmParseDataFrameFileTool = createTool(
    `${DATA_FRAME_TOOL_PREFIX}_ask_user_to_confirm_parse_data_frame_file`,
    'Asks the user to confirm the data frame creation from file, if there are multiple sheets in the file as which sheet should be transformed to data frames.',
  )
    .setCallback(() => {})
    .setCategory('client-exec-tool')
    .build();

  static chooseToolToRender = (tool: ThreadToolUsageContent) => {
    switch (tool.name) {
      case DataFrameClientTools.askUserToConfirmParseDataFrameFileTool.name:
        return <DataFrameConfirmParseDataFrameFile key={tool.content_id} tool={tool} />;
      case SERVER_TOOLS_THAT_REQUIRE_CLIENT_ACTION.CREATE_FROM_FILE:
      case SERVER_TOOLS_THAT_REQUIRE_CLIENT_ACTION.CREATE_FROM_SQL:
        if (tool.complete) {
          return <DataFrameCallbackDataFrameCreation key={tool.content_id} tool={tool} />;
        }
        return null;
      default:
        return null;
    }
  };

  /**
   * Export all client tools for Data Frames
   */
  static clientToolsList = [{ ...DataFrameClientTools.askUserToConfirmParseDataFrameFileTool }];
}
