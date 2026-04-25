import * as React from 'react';
import { cn } from './utils';

interface CardProps {
  children: React.ReactNode;
  className?: string;
}

export function Card({ children, className }: CardProps) {
  return (
    <div className={cn('bg-white rounded-xl border shadow-sm', className)}>
      {children}
    </div>
  );
}

export function CardHeader({ children, className }: CardProps) {
  return <div className={cn('px-6 py-4 border-b', className)}>{children}</div>;
}

export function CardBody({ children, className }: CardProps) {
  return <div className={cn('px-6 py-4', className)}>{children}</div>;
}
