import Image from 'next/image';

interface CeltmLogoProps {
  compact?: boolean;
  className?: string;
  imageClassName?: string;
  alt?: string;
}

export default function CeltmLogo({
  compact = false,
  className = '',
  imageClassName = '',
  alt = 'CELTM',
}: CeltmLogoProps) {
  if (compact) {
    return (
      <div className={`relative h-8 w-10 overflow-hidden ${className}`}>
        <Image
          src="/celtm-logo-cropped.png"
          alt={alt}
          width={180}
          height={48}
          priority
          className={`absolute left-0 top-1/2 h-full w-auto max-w-none -translate-y-1/2 object-contain object-left ${imageClassName}`}
        />
      </div>
    );
  }

  return (
    <div className={`inline-flex items-center overflow-hidden ${className}`}>
      <Image
        src="/celtm-logo-cropped.png"
        alt={alt}
        width={180}
        height={48}
        priority
        className={`h-full w-auto max-w-full object-contain object-left ${imageClassName}`}
      />
    </div>
  );
}
