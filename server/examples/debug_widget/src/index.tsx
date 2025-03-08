import React from "react";
import { createRender } from "@anywidget/react";
import { App } from "./App";
import "./index.css";

export const render = createRender(() => {
  return <App />;
});