import React from 'react';

export interface SegmentOption<T extends string> {
  value: T;
  label: string;
  icon?: React.ReactNode;
  count?: number;
}

interface SegmentedControlProps<T extends string> {
  id: string;
  label: string;
  options: SegmentOption<T>[];
  value: T;
  onChange: (value: T) => void;
  size?: 'sm' | 'md';
}

export function SegmentedControl<T extends string>({
  id,
  label,
  options,
  value,
  onChange,
  size = 'md',
}: SegmentedControlProps<T>) {
  const sizeClasses = size === 'sm' ? 'text-xs py-1 px-2.5' : 'text-sm py-1.5 px-3.5';

  return (
    <div className="flex flex-col gap-1.5">
      <span id={`${id}-group-label`} className="sr-only">
        {label}
      </span>
      <div
        role="group"
        aria-labelledby={`${id}-group-label`}
        className="inline-flex p-1 bg-slate-900 border border-slate-800 rounded-lg max-w-full overflow-x-auto gap-1"
      >
        {options.map((option) => {
          const isSelected = option.value === value;
          return (
            <button
              key={option.value}
              type="button"
              aria-pressed={isSelected}
              onClick={() => onChange(option.value)}
              className={`${sizeClasses} inline-flex items-center gap-2 rounded-md font-medium transition-all duration-150 focus:outline-none focus-visible:ring-2 focus-visible:ring-amberline focus-visible:ring-offset-1 focus-visible:ring-offset-slate-900 active:scale-[0.98] ${
                isSelected
                  ? 'bg-amberline text-slate-950 font-semibold shadow-sm'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
              }`}
            >
              {option.icon && (
                <span className="shrink-0" aria-hidden="true">
                  {option.icon}
                </span>
              )}
              <span>{option.label}</span>
              {typeof option.count === 'number' && (
                <span
                  className={`text-[10px] font-mono px-1.5 py-0.5 rounded-full ${
                    isSelected
                      ? 'bg-amberline-700/30 text-slate-950 font-bold'
                      : 'bg-slate-800 text-slate-400'
                  }`}
                >
                  {option.count}
                </span>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}
