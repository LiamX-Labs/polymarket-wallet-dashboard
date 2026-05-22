import { useState } from 'react';

interface WalletAddressProps {
  address: string;
}

export function WalletAddress({ address }: WalletAddressProps) {
  const [showFull, setShowFull] = useState(false);
  const [copied, setCopied] = useState(false);

  const shortAddress = `${address.slice(0, 6)}...${address.slice(-4)}`;

  const handleCopy = async (e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await navigator.clipboard.writeText(address);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };

  const handleClick = () => {
    setShowFull(!showFull);
  };

  return (
    <div className="relative">
      <div
        onClick={handleClick}
        className="cursor-pointer hover:text-accent-blue transition-colors text-xs"
      >
        {showFull ? address : shortAddress}
      </div>
      {showFull && (
        <button
          onClick={handleCopy}
          className="mt-1 px-2 py-1 text-xs bg-dark-border hover:bg-accent-blue/20 rounded transition-colors"
        >
          {copied ? '✓ Copied!' : 'Copy'}
        </button>
      )}
    </div>
  );
}
