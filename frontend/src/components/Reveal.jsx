import useReveal from '../hooks/useReveal'

/**
 * Wraps children in a fade/slide-in animation triggered on scroll.
 *
 *   <Reveal variant="left" delay={120}>...</Reveal>
 */
export default function Reveal({
  children,
  variant = 'up',
  delay = 0,
  as: Tag = 'div',
  className = '',
  ...rest
}) {
  const ref = useReveal()
  const variantClass = variant === 'up' ? '' : `reveal--${variant}`

  return (
    <Tag
      ref={ref}
      className={`reveal ${variantClass} ${className}`.trim()}
      style={delay ? { '--reveal-delay': `${delay}ms` } : undefined}
      {...rest}
    >
      {children}
    </Tag>
  )
}
