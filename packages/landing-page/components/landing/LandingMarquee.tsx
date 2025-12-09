import clsx from 'clsx';

/**
 * A component meant to be used in the landing page.
 * It displays a marquee of elements and loops through them.
 * Uses pure CSS for animation - no JavaScript calculations.
 */
export const LandingMarquee = ({
  className,
  children,
  innerClassName,
  withBackground = false,
  animationDurationInSeconds = 30,
  animationDirection,
  variant = 'primary',
}: {
  className?: string;
  innerClassName?: string;
  children?: React.ReactNode;
  withBackground?: boolean;
  animationDurationInSeconds?: number;
  animationDirection?: 'left' | 'right';
  variant?: 'primary' | 'secondary';
}) => {
  return (
    <div
      className={clsx(
        'w-full overflow-hidden flex items-center py-4 lg:py-8',
        withBackground && variant === 'primary'
          ? 'bg-primary-100/20 dark:bg-primary-900/10'
          : '',
        withBackground && variant === 'secondary'
          ? 'bg-secondary-100/20 dark:bg-secondary-900/10'
          : '',
        className,
      )}
    >
      <div
        className={clsx(
          'flex animate-marquee',
          animationDirection === 'left' ? 'direction-reverse' : '',
          innerClassName,
        )}
        style={{
          animationDuration: `${animationDurationInSeconds}s`,
        }}
      >
        {/* Render children twice for seamless looping */}
        {[...Array(2)].map((_, groupIndex) => (
          <div key={groupIndex} className="flex items-center flex-shrink-0">
            {Array.isArray(children)
              ? children.map((child, childIndex) => (
                  <div
                    key={`${groupIndex}-${childIndex}`}
                    className="flex items-center justify-center flex-shrink-0"
                  >
                    {child}
                  </div>
                ))
              : children}
          </div>
        ))}
      </div>
    </div>
  );
};
