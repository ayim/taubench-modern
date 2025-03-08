import React from "react";
import { DebugWidget } from "./components/DebugWidget";

// Provide a top-level component that receives traitlets
// from the widget. The "useModelState" is from @anywidget/react
import { useModelState, useModel } from "@anywidget/react";

export const App: React.FC = () => {
  // We'll ask for "threads", "messages", etc. from the Python side
  const [threads] = useModelState<any>("threads");
  const [messages] = useModelState<any>("messages");
  const [selectedThreadId] = useModelState<any>("selected_thread_id");
  const [selectedThreadName] = useModelState<any>("selected_thread_name");
  const [isLoading] = useModelState<any>("is_loading");
  const [statusMessage] = useModelState<any>("status_message");

  // You can also get "widget" from the context, so you can call .send(...)
  // to pass messages to the Python side.  Alternatively, you can rely on
  // onMsg in Python if you prefer manual merges.

  const model = useModel();

  const handleSendMsgToPython = (msg: any) => {
    model?.send(msg);
  };

  return (
    <DebugWidget
      threads={threads || []}
      selected_thread_id={selectedThreadId}
      selected_thread_name={selectedThreadName}
      messages={messages || []}
      is_loading={isLoading}
      status_message={statusMessage}
      sendMsgToPython={handleSendMsgToPython}
    />
  );
};
