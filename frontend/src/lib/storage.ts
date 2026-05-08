const ABSOLUTE_URL_PATTERN = /^https?:\/\//i;
const SUPABASE_PUBLIC_PATH_PATTERN = /^\/?storage\/v1\/object\/public\//i;

export function resolveStorageAssetUrl(
  path: string | null | undefined,
  fallbackBucket = "profile-assets",
): string | null {
  if (!path) {
    return null;
  }
  const trimmedPath = path.trim();
  if (!trimmedPath) {
    return null;
  }
  
  // Handle absolute URLs
  if (ABSOLUTE_URL_PATTERN.test(trimmedPath)) {
    return trimmedPath;
  }

  const baseUrl = (process.env.NEXT_PUBLIC_SUPABASE_URL || "").replace(/\/$/, "");
  
  // If we already have the full Supabase public path, just prepend the base URL if missing
  if (SUPABASE_PUBLIC_PATH_PATTERN.test(trimmedPath)) {
    const cleanPath = trimmedPath.replace(/^\/+/, "");
    return baseUrl ? `${baseUrl}/${cleanPath}` : cleanPath;
  }

  const normalizedPath = trimmedPath.replace(/^\/+/, "");
  
  // If the path already includes a bucket name (segment/segment)
  const segments = normalizedPath.split("/");
  if (segments.length >= 2) {
    return baseUrl 
      ? `${baseUrl}/storage/v1/object/public/${normalizedPath}`
      : normalizedPath;
  }

  // Fallback to default bucket
  return baseUrl 
    ? `${baseUrl}/storage/v1/object/public/${fallbackBucket}/${normalizedPath}`
    : normalizedPath;
}
