import React from 'react';

interface ToggleSwitchProps {
  id: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
  label: string;
  description?: string;
  disabled?: boolean;
}

export const ToggleSwitch: React.FC<ToggleSwitchProps> = ({
  id,
  checked,
  onChange,
  label,
  description,
  disabled = false,
}) => {
  const handleKeyDown = (e: React.KeyboardEvent<HTMLButtonElement>) => {
    if (disabled) return;
    if (e.key === ' ' || e.key === 'Enter') {
      e.preventDefault();
      onChange(!checked);
    }
  };

  return (
    <div className="flex items-start justify-between gap-4 py-2">
      <div className="flex flex-col">
        <label
          id={`${id}-label`}
          htmlFor={id}
          className={`text-sm font-medium ${
            disabled ? 'text-slate-400' : 'text-slate-200 cursor-pointer'
          }`}
          onClick={() => !disabled && onChange(!checked)}
        >
          {label}
        </label>
        {description && (
          <p id={`${id}-desc`} className="text-xs text-slate-400 mt-0.5">
            {description}
          </p>
        )}
      </div>

      <button
        type="button"
        id={id}
        role="switch"
        aria-checked={checked}
        aria-labelledby={`${id}-label`}
        aria-describedby={description ? `${id}-desc` : undefined}
        disabled={disabled}
        onClick={() => !disabled && onChange(!checked)}
        onKeyDown={handleKeyDown}
        className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus-visible:ring-2 focus-visible:ring-amberline focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950 active:scale-95 disabled:cursor-not-allowed disabled:opacity-50 ${
          checked ? 'bg-amberline' : 'bg-slate-700'
        }`}
      >
        <span
          aria-hidden="true"
          className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-slate-950 shadow ring-0 transition duration-200 ease-in-out ${
            checked ? 'translate-x-5 bg-slate-950' : 'translate-x-0 bg-slate-300'
          }`}
        />
      </button>
    </div>
  );
};
