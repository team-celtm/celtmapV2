const ABSOLUTE_URL_PATTERN = /^https?:\/\//i;
const SUPABASE_PUBLIC_PATH_PATTERN = /^\/?storage\/v1\/object\/public\//i;

function requiredEnvUrl(value: string | undefined, name: string): string {
  if (!value || value === "undefined" || value === "null" || !value.trim()) {
    throw new Error(`${name} must be configured for hosted asset URLs.`);
  }
  return value.replace(/\/$/, "");
}

export function resolveStorageAssetUrl(
  path: string | null | undefined,
  bucket = "profile-assets",
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

  if (trimmedPath.startsWith("supabase://")) {
    return null;
  }

  if (trimmedPath.startsWith("/files/")) {
    const apiBase = requiredEnvUrl(process.env.NEXT_PUBLIC_API_BASE_URL, "NEXT_PUBLIC_API_BASE_URL")
      .replace(/\/api\/v1$/, "");
    return `${apiBase}${trimmedPath}`;
  }

  const baseUrl = requiredEnvUrl(process.env.NEXT_PUBLIC_SUPABASE_URL, "NEXT_PUBLIC_SUPABASE_URL");
  
  // If we already have the full Supabase public path, just prepend the base URL if missing
  if (SUPABASE_PUBLIC_PATH_PATTERN.test(trimmedPath)) {
    const cleanPath = trimmedPath.replace(/^\/+/, "");
    return `${baseUrl}/${cleanPath}`;
  }

  const normalizedPath = trimmedPath.replace(/^\/+/, "");
  
  // If the path already includes a bucket name (segment/segment)
  const segments = normalizedPath.split("/");
  if (segments.length >= 2) {
    return `${baseUrl}/storage/v1/object/public/${normalizedPath}`;
  }

  return `${baseUrl}/storage/v1/object/public/${bucket}/${normalizedPath}`;
}
