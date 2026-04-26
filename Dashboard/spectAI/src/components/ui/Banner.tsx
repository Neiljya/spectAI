// src/components/ui/Banner.tsx
import { ReactNode } from 'react';
import './Banner.css'; // Assuming you are using standard CSS like your LoginForm

interface BannerProps {
  type: 'success' | 'error' | 'warning' | 'info';
  children: ReactNode;
  onDismiss?: () => void; // Optional: allows the user to close the banner
}

export function Banner({ type, children, onDismiss }: BannerProps) {
  return (
    <div className={`banner banner--${type}`} role="alert">
      <div className="banner__content">
        {children}
      </div>
      
      {/* Only show the close button if an onDismiss function is provided */}
      {onDismiss && (
        <button 
          type="button" 
          className="banner__close" 
          onClick={onDismiss}
          aria-label="Close banner"
        >
          &times;
        </button>
      )}
    </div>
  );
}