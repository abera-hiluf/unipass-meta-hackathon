export function Button({ children, variant = 'primary', className = '', ...props }) {
  const styles = variant === 'secondary' ? 'border border-slate-200 bg-white text-ink hover:bg-slate-50' : variant === 'ghost' ? 'text-slate-600 hover:bg-slate-100' : 'bg-ink text-white hover:bg-slate-800'
  return <button className={`rounded-xl px-5 py-3 text-sm font-semibold transition focus:outline-none focus:ring-2 focus:ring-signal/40 disabled:cursor-not-allowed disabled:opacity-50 ${styles} ${className}`} {...props}>{children}</button>
}
