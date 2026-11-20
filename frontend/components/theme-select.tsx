"use client";

import { useEffect, useRef } from "react";

export function ThemeSelect() {
  const select = useRef<HTMLSelectElement>(null);
  useEffect(() => {
    const sync = () => {
      if (select.current) {
        select.current.value = document.documentElement.dataset.themePreference || "system";
      }
    };
    sync();
    window.addEventListener("storage", sync);
    return () => window.removeEventListener("storage", sync);
  }, []);

  return (
    <select
      ref={select}
      className="theme-select"
      aria-label="Color theme"
      defaultValue="system"
      onChange={(event) => window.dispatchEvent(new CustomEvent("seoci-theme-change", { detail: event.target.value }))}
    >
      <option value="system">System theme</option>
      <option value="light">Light theme</option>
      <option value="dark">Dark theme</option>
    </select>
  );
}
