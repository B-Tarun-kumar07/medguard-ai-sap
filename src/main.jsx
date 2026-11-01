import React from "react";
import { createRoot } from "react-dom/client";
import { ThemeProvider } from "@ui5/webcomponents-react";
import "@ui5/webcomponents-react/dist/Assets.js";
import App from "./App.jsx";
import "./styles.css";

createRoot(document.getElementById("root")).render(
  <React.StrictMode><ThemeProvider><App /></ThemeProvider></React.StrictMode>
);
