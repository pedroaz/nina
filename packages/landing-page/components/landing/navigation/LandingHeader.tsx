import { Button } from '@/components/shared/ui/button';
import clsx from 'clsx';
import Link from 'next/link';

export interface LandingHeaderProps {
  /**
   * Logo text or React element
   * @default "Nina"
   */
  logo?: React.ReactNode;

  /**
   * Additional CSS classes
   */
  className?: string;

  /**
   * Positioning behavior
   * @default "sticky"
   */
  position?: 'sticky' | 'fixed' | 'relative';

  /**
   * Color variant
   * @default "primary"
   */
  variant?: 'primary' | 'secondary';
}

/**
 * Minimalistic landing page header with logo and navigation
 */
export const LandingHeader = ({
  logo = 'Nina',
  className,
  position = 'sticky',
  variant = 'primary',
}: LandingHeaderProps) => {
  return (
    <header
      className={clsx(
        'w-full z-50 backdrop-blur-sm',
        'border-b border-gray-100 dark:border-neutral-800',
        'bg-white/80 dark:bg-gray-950/80',
        position === 'sticky' && 'sticky top-0',
        position === 'fixed' && 'fixed top-0',
        position === 'relative' && 'relative',
        className
      )}
    >
      <div className="w-full max-w-full flex items-center justify-between px-6 py-4 mx-auto container-wide">
        {/* Logo */}
        <Link
          href="/"
          className={clsx(
            'text-xl font-semibold font-display',
            'text-black dark:text-white',
            'transition-colors hover:text-primary-500 dark:hover:text-primary-400'
          )}
        >
          {logo}
        </Link>

        {/* Navigation */}
        <nav className="flex items-center gap-4">
          <Link
            href="/blog"
            className={clsx(
              'text-base font-medium',
              'text-black dark:text-gray-200',
              'transition-colors',
              variant === 'primary'
                ? 'hover:text-primary-500 dark:hover:text-primary-400'
                : 'hover:text-secondary-500 dark:hover:text-secondary-400'
            )}
          >
            Blog
          </Link>

          <Button
            size="default"
            variant={variant === 'primary' ? 'default' : 'secondary'}
            asChild
          >
            <Link href="/">Start</Link>
          </Button>
        </nav>
      </div>
    </header>
  );
};
