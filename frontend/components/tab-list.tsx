"use client";
import type { ReactNode } from "react";

export function TabList({
  id, label, tabs, selected, onSelect, className = "tabs",
}: {
  id: string;
  label: string;
  tabs: { id: string; content: ReactNode }[];
  selected: string;
  onSelect: (id: string) => void;
  className?: string;
}) {
  return (
    <div className={className} role="tablist" aria-label={label}>
      {tabs.map((tab, index) => (
        <button
          key={tab.id}
          id={`${id}-tab-${tab.id}`}
          role="tab"
          aria-selected={selected === tab.id}
          aria-controls={`${id}-panel-${tab.id}`}
          tabIndex={selected === tab.id ? 0 : -1}
          onClick={() => onSelect(tab.id)}
          onKeyDown={(event) => {
            const next = event.key === "ArrowRight" ? (index + 1) % tabs.length
              : event.key === "ArrowLeft" ? (index + tabs.length - 1) % tabs.length
              : event.key === "Home" ? 0 : event.key === "End" ? tabs.length - 1 : -1;
            if (next < 0) return;
            event.preventDefault();
            onSelect(tabs[next].id);
            document.getElementById(`${id}-tab-${tabs[next].id}`)?.focus();
          }}
        >
          {tab.content}
        </button>
      ))}
    </div>
  );
}
