import React from 'react';

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'outline' | 'danger' | 'ghost';
  size?: 'sm' | 'md' | 'lg';
  isLoading?: boolean;
  disabledReason?: string;
  icon?: React.ReactNode;
}

export const Button: React.FC<ButtonProps> = ({
  children,
  variant = 'primary',
  size = 'md',
  isLoading = false,
  disabledReason,
  disabled = false,
  type = 'button',
  icon,
  className = '',
  onClick,
  ...props
}) => {
  const isEffectivelyDisabled = disabled || isLoading;

  const baseStyles =
    'relative inline-flex items-center justify-center font-medium transition-all duration-150 rounded-lg select-none focus:outline-none focus-visible:ring-2 focus-visible:ring-amberline focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950 active:scale-[0.98] disabled:active:scale-100 disabled:cursor-not-allowed disabled:opacity-50';

  const sizeStyles = {
    sm: 'text-xs px-2.5 py-1.5 gap-1.5',
    md: 'text-sm px-4 py-2 gap-2',
    lg: 'text-base px-5 py-2.5 gap-2.5',
  }[size];

  const variantStyles = {
    primary:
      'bg-amberline hover:bg-amber-500 text-slate-950 font-semibold shadow-sm hover:shadow-amber-500/20 active:bg-amber-600',
    secondary:
      'bg-slate-800 hover:bg-slate-700 text-slate-100 border border-slate-700/80 active:bg-slate-800',
    outline:
      'bg-transparent hover:bg-slate-800/60 text-slate-200 border border-slate-700 active:bg-slate-800/80',
    danger:
      'bg-rose-600 hover:bg-rose-500 text-white shadow-sm active:bg-rose-700',
    ghost:
      'bg-transparent hover:bg-slate-800 text-slate-300 hover:text-slate-100 active:bg-slate-800/80',
  }[variant];

  const buttonElement = (
    <button
      type={type}
      disabled={isEffectivelyDisabled}
      aria-disabled={isEffectivelyDisabled}
      aria-busy={isLoading}
      onClick={isEffectivelyDisabled ? undefined : onClick}
      className={`${baseStyles} ${sizeStyles} ${variantStyles} ${
        disabledReason && isEffectivelyDisabled ? 'pointer-events-none' : ''
      } ${className}`}
      {...props}
    >
      {isLoading && (
        <svg
          className="animate-spin -ml-0.5 h-4 w-4 text-current"
          xmlns="http://www.w3.org/2000/svg"
          fill="none"
          viewBox="0 0 24 24"
          aria-hidden="true"
        >
          <circle
            className="opacity-25"
            cx="12"
            cy="12"
            r="10"
            stroke="currentColor"
            strokeWidth="4"
          />
          <path
            className="opacity-75"
            fill="currentColor"
            d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
          />
        </svg>
      )}
      {!isLoading && icon && <span className="inline-flex shrink-0" aria-hidden="true">{icon}</span>}
      <span>{children}</span>
    </button>
  );

  // Accessible tooltip wrapper for disabled states according to .Jules/palette.md:
  // When providing a reason for a disabled button, wrap it in a focusable <span> (tabIndex={0}) with cursor-not-allowed,
  // and set pointer-events-none on the button itself so the wrapper can show the title.
  // Also apply group and focus:outline-none to the wrapper, and use group-focus-visible:ring-* on child so focus rings inherit rounded styling.
  if (isEffectivelyDisabled && disabledReason) {
    return (
      <span
        tabIndex={0}
        title={disabledReason}
        aria-label={disabledReason}
        className="group inline-flex focus:outline-none cursor-not-allowed rounded-lg"
      >
        {buttonElement}
      </span>
    );
  }

  return buttonElement;
};
