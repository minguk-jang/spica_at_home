import React from "react";

export function SummaryItem({ label, value }: { label: string; value: string }): React.ReactElement {
  return (
    <div className="summaryItem">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

export function SegmentedControl(props: {
  label: string;
  value: string;
  options: Array<{ value: string; label: string; title: string }>;
  onChange: (value: string) => void;
}): React.ReactElement {
  return (
    <fieldset className="segmentedField">
      <legend>{props.label}</legend>
      <div className="segmentedControl">
        {props.options.map((option) => (
          <button
            key={option.value}
            className={props.value === option.value ? "segment active" : "segment"}
            type="button"
            title={option.title}
            aria-pressed={props.value === option.value}
            onClick={() => props.onChange(option.value)}
          >
            {option.label}
          </button>
        ))}
      </div>
    </fieldset>
  );
}

export function TextField(props: {
  label: string;
  value: string;
  onChange: (value: string) => void;
}): React.ReactElement {
  return (
    <label className="textField">
      <span>{props.label}</span>
      <input value={props.value} onChange={(event) => props.onChange(event.target.value)} />
    </label>
  );
}

export function SelectField(props: {
  label: string;
  value: string;
  options: string[];
  onChange: (value: string) => void;
}): React.ReactElement {
  return (
    <label className="textField">
      <span>{props.label}</span>
      <select value={props.value} onChange={(event) => props.onChange(event.target.value)}>
        {props.options.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    </label>
  );
}

export function NumberField(props: {
  label: string;
  value: number;
  onChange: (value: number) => void;
}): React.ReactElement {
  return (
    <label className="textField compact">
      <span>{props.label}</span>
      <input
        type="number"
        min={0}
        max={10}
        value={props.value}
        onChange={(event) => props.onChange(Number(event.target.value))}
      />
    </label>
  );
}

export function CheckboxField(props: {
  label: string;
  checked: boolean;
  onChange: (value: boolean) => void;
}): React.ReactElement {
  return (
    <label className="checkboxField">
      <input
        type="checkbox"
        checked={props.checked}
        onChange={(event) => props.onChange(event.target.checked)}
      />
      <span>{props.label}</span>
    </label>
  );
}

export function IconButton(props: {
  label: string;
  title: string;
  disabled?: boolean;
  variant?: "primary" | "success" | "plain";
  onClick: () => void;
  children: React.ReactNode;
}): React.ReactElement {
  return (
    <button
      className={props.variant ? `iconButton ${props.variant}` : "iconButton"}
      aria-label={props.label}
      title={props.title}
      disabled={props.disabled}
      onClick={props.onClick}
    >
      {props.children}
    </button>
  );
}

export function IconTextButton(props: {
  label: string;
  title: string;
  disabled?: boolean;
  onClick: () => void;
  children: React.ReactNode;
}): React.ReactElement {
  return (
    <button
      className="iconButton"
      aria-label={props.label}
      title={props.title}
      disabled={props.disabled}
      onClick={props.onClick}
    >
      {props.children}
      <span className="srOnly">{props.label}</span>
    </button>
  );
}

export function SectionTitle({ icon, title }: { icon: React.ReactNode; title: string }): React.ReactElement {
  return (
    <div className="sectionTitle">
      {icon}
      <h3>{title}</h3>
    </div>
  );
}

export function Metric({ label, value }: { label: string; value: number }): React.ReactElement {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

export function Badge({ children }: { children: React.ReactNode }): React.ReactElement {
  return <span className="badge">{children}</span>;
}

export function StatusPill({ status, label = status }: { status: string; label?: string }): React.ReactElement {
  return <span className={`statusPill ${status}`}>{label}</span>;
}

export function JsonBlock({ value, compact = false }: { value: unknown; compact?: boolean }): React.ReactElement {
  return <pre className={compact ? "jsonBlock compact" : "jsonBlock"}>{pretty(value)}</pre>;
}

function pretty(value: unknown): string {
  if (value === undefined || value === null) {
    return "";
  }
  if (typeof value === "string") {
    return value;
  }
  return JSON.stringify(value, null, 2);
}
