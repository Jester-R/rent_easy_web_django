/** Coordinate helpers ported from Flutter's lib/utils/coordinate_parser.dart. */

export interface Coordinates {
  latitude: number;
  longitude: number;
}

const PAIR = /(-?\d{1,3}(?:\.\d+)?)[\s,;]+(-?\d{1,3}(?:\.\d+)?)/;
const NAMED =
  /(?:lat|latitude|la)\s*[=:]\s*(-?\d{1,3}(?:\.\d+)?)|(?:lng|lon|long|longitude|lo)\s*[=:]\s*(-?\d{1,3}(?:\.\d+)?)/gi;

function valid(latitude: number, longitude: number): Coordinates | null {
  if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) return null;
  if (latitude < -90 || latitude > 90) return null;
  if (longitude < -180 || longitude > 180) return null;
  if (latitude === 0 && longitude === 0) return null;
  return { latitude, longitude };
}

/**
 * Parse a coordinate pair out of a pasted value. Supports:
 * - "11.5564, 104.9282" / "11.5564 104.9282"
 * - Google Maps URLs (`@lat,lng`, `?q=lat,lng`, `!3dlat!4dlng`)
 * - query strings with `lat=`/`lng=` params
 */
export function parseCoordinates(input: string | null | undefined): Coordinates | null {
  if (!input) return null;
  const text = String(input).trim();
  if (!text) return null;

  const named: Record<string, number> = {};
  let match: RegExpExecArray | null;
  NAMED.lastIndex = 0;
  while ((match = NAMED.exec(text)) !== null) {
    const key = match[1] !== undefined ? 'lat' : 'lng';
    named[key] = Number(match[1] ?? match[2]);
  }
  if (named['lat'] !== undefined && named['lng'] !== undefined) {
    return valid(named['lat'], named['lng']);
  }

  const bang = text.match(/!3d(-?\d+(?:\.\d+)?)!4d(-?\d+(?:\.\d+)?)/);
  if (bang) return valid(Number(bang[1]), Number(bang[2]));

  const at = text.match(/@(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)/);
  if (at) return valid(Number(at[1]), Number(at[2]));

  const pair = text.match(PAIR);
  if (pair) return valid(Number(pair[1]), Number(pair[2]));

  return null;
}

/** "11.5564, 104.9282" at 6 decimal places. */
export function formatCoordinates(latitude?: number | null, longitude?: number | null): string {
  if (latitude == null || longitude == null) return '';
  return `${latitude.toFixed(6)}, ${longitude.toFixed(6)}`;
}

export function googleMapsUrl(latitude: number, longitude: number): string {
  return `https://www.google.com/maps/search/?api=1&query=${latitude},${longitude}`;
}
