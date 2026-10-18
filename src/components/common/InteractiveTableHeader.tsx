import React from 'react';

export type SortDirection = 'asc' | 'desc' | null;

interface InteractiveTableHeaderProps {
  label: string;
  field: string;
  currentSortField: string | null;
  direction: SortDirection;
  onSort: (field: string) => void;
  align?: 'left' | 'center' | 'right';
  className?: string;
}

export const InteractiveTableHeader: React.FC<InteractiveTableHeaderProps> = ({
  label,
  field,
  currentSortField,
  direction,
  onSort,
  align = 'left',
  className = '',
}) => {
  const isCurrent = currentSortField === field;
  const nextDirection = isCurrent && direction === 'asc' ? 'descending' : 'ascending';
  const alignClass = align === 'right' ? 'justify-end' : align === 'center' ? 'justify-center' : 'justify-start';

  return (
    <th
      scope="col"
      className={`px-4 py-3 text-xs font-semibold uppercase tracking-wider text-slate-400 ${
        align === 'right' ? 'text-right' : align === 'center' ? 'text-center' : 'text-left'
      } ${className}`}
    >
      <button
        type="button"
        onClick={() => onSort(field)}
        aria-label={`Sort by ${label} ${nextDirection}`}
        className={`group inline-flex items-center gap-1.5 rounded py-1 px-1.5 -mx-1.5 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-amberline ${alignClass} hover:text-slate-200`}
      >
        <span>{label}</span>
        <span className="flex flex-col text-[10px] leading-none shrink-0" aria-hidden="true">
          {isCurrent ? (
            direction === 'asc' ? (
              <svg className="w-3.5 h-3.5 text-amberline" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M14.707 12.707a1 1 0 01-1.414 0L10 9.414l-3.293 3.293a1 1 0 01-1.414-1.414l4-4a1 1 0 011.414 0l4 4a1 1 0 010 1.414z" clipRule="evenodd" />
              </svg>
            ) : (
              <svg className="w-3.5 h-3.5 text-amberline" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clipRule="evenodd" />
              </svg>
            )
          ) : (
            <svg className="w-3.5 h-3.5 text-slate-600 group-hover:text-slate-400" viewBox="0 0 20 20" fill="currentColor">
              <path d="M5 8l5-5 5 5H5zm10 4l-5 5-5-5h10z" />
            </svg>
          )}
        </span>
      </button>
    </th>
  );
};
