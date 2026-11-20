"use client";

import { useEffect, useRef } from "react";

export function TextSizeSelect() {
  const select = useRef<HTMLSelectElement>(null);
  useEffect(() => {
    const sync = () => {
      if (select.current) {
        select.current.value = document.documentElement.dataset.textSize || "normal";
      }
    };
    sync();
    window.addEventListener("storage", sync);
    window.addEventListener("seoci-text-size-change", sync);
    return () => {
      window.removeEventListener("storage", sync);
      window.removeEventListener("seoci-text-size-change", sync);
    };
  }, []);

  return (
    <select
      ref={select}
      className="theme-select"
      aria-label="Text size"
      defaultValue="normal"
      onChange={(event) => window.dispatchEvent(new CustomEvent("seoci-text-size-change", { detail: event.target.value }))}
    >
      <option value="small">Small text</option>
      <option value="normal">Normal text</option>
      <option value="large">Large text</option>
    </select>
  );
}
