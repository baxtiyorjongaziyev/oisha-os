import React, { useRef } from 'react';
import { Search, X } from 'lucide-react';

interface AccessibleSearchInputProps {
  id: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  label?: string;
  className?: string;
}

export const AccessibleSearchInput: React.FC<AccessibleSearchInputProps> = ({
  id,
  value,
  onChange,
  placeholder = 'Search...',
  label = 'Search',
  className = '',
}) => {
  const inputRef = useRef<HTMLInputElement>(null);

  const handleClear = () => {
    onChange('');
    // Programmatically return focus to the input field as required by .Jules/palette.md line 87
    inputRef.current?.focus();
  };

  return (
    <div className={`relative flex items-center ${className}`}>
      <label htmlFor={id} className="sr-only">
        {label}
      </label>
      <div className="absolute left-3 pointer-events-none text-slate-500 flex items-center" aria-hidden="true">
        <Search className="w-4 h-4" />
      </div>
      <input
        ref={inputRef}
        type="search"
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full pl-9 pr-9 py-2 bg-slate-900 border border-slate-800 rounded-lg text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus-visible:ring-2 focus-visible:ring-amberline focus-visible:border-transparent transition-colors"
      />
      {value.length > 0 && (
        <button
          type="button"
          onClick={handleClear}
          aria-label={`Clear ${label.toLowerCase()} text`}
          className="absolute right-2.5 p-1 text-slate-400 hover:text-slate-100 rounded-md transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-amberline"
        >
          <X className="w-4 h-4" />
        </button>
      )}
    </div>
  );
};
