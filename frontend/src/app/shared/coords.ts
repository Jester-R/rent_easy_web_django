/** Coordinate helpers ported from Flutter's lib/utils/coordinate_parser.dart. */

export interface Coordinates {
  latitude: number;
  longitude: number;
}

const PAIR = /(-?\d{1,3}(?:\.\d+)?)[\s,;]+(-?\d{1,3}(?:\.\d+)?)/;
const NAMED =
  /(?:lat|latitude|la)\s*[=:]\s*(-?\d{1,3}(?:\.\d+)?)|(?:lng|lon|long|longitude|lo)\s*[=:]\s*(-?\d{1,3}(?:\.\d+)?)/gi;

const DMS_REGEX =
  /(\d{1,3})[°\s]+(\d{1,2})['\s]+([\d.]+)(?:\"|\'\')?\s*([NSns])[\s,;]+(\d{1,3})[°\s]+(\d{1,2})['\s]+([\d.]+)(?:\"|\'\')?\s*([EWew])/i;

function valid(latitude: number, longitude: number): Coordinates | null {
  if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) return null;
  if (latitude < -90 || latitude > 90) return null;
  if (longitude < -180 || longitude > 180) return null;
  if (latitude === 0 && longitude === 0) return null;
  return { latitude, longitude };
}

function parseDms(input: string): Coordinates | null {
  const m = input.match(DMS_REGEX);
  if (!m) return null;
  const latDeg = parseFloat(m[1]);
  const latMin = parseFloat(m[2]);
  const latSec = parseFloat(m[3]);
  const latHem = m[4].toUpperCase();

  const lngDeg = parseFloat(m[5]);
  const lngMin = parseFloat(m[6]);
  const lngSec = parseFloat(m[7]);
  const lngHem = m[8].toUpperCase();

  let lat = latDeg + latMin / 60 + latSec / 3600;
  let lng = lngDeg + lngMin / 60 + lngSec / 3600;
  if (latHem === 'S') lat = -lat;
  if (lngHem === 'W') lng = -lng;
  return valid(lat, lng);
}

/**
 * Parse a coordinate pair out of a pasted value. Supports:
 * - "11.5564, 104.9282" / "11.5564 104.9282"
 * - DMS ("11°33'23.0\"N 104°55'41.5\"E")
 * - Google Maps URLs (`@lat,lng`, `?q=lat,lng`, `!3dlat!4dlng`, `!2dlng!3dlat`)
 * - query strings with `lat=`/`lng=`/`markers=`/`center=` params
 * - iframe embed codes
 */
export function parseCoordinates(input: string | null | undefined): Coordinates | null {
  if (!input) return null;
  let text = String(input).trim();
  if (!text) return null;

  // Unescape URL encoded strings if present
  try {
    text = decodeURIComponent(text);
  } catch {
    // Keep text as-is if malformed percent encoding
  }

  // Check DMS format
  const dms = parseDms(text);
  if (dms) return dms;

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

  // Google Maps path search/place: /maps/search/11.587689,+104.922923 or /maps/place/11.587689,+104.922923
  const searchPath = text.match(
    /\/(?:maps\/)?(?:search|place)\/(-?\d+(?:\.\d+)?),?\s*(?:\+|%20|\s)*(-?\d+(?:\.\d+)?)/i
  );
  if (searchPath) return valid(Number(searchPath[1]), Number(searchPath[2]));

  // Google embed iframe: !2d<lng>!3d<lat>
  const embed = text.match(/!2d(-?\d+(?:\.\d+)?)!3d(-?\d+(?:\.\d+)?)/i);
  if (embed) return valid(Number(embed[2]), Number(embed[1]));

  const bang = text.match(/!3d(-?\d+(?:\.\d+)?)!4d(-?\d+(?:\.\d+)?)/i);
  if (bang) return valid(Number(bang[1]), Number(bang[2]));

  const data3d4d = text.match(/3d(-?\d+(?:\.\d+)?)\D+?4d(-?\d+(?:\.\d+)?)/i);
  if (data3d4d) return valid(Number(data3d4d[1]), Number(data3d4d[2]));

  const at = text.match(/@(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)/);
  if (at) return valid(Number(at[1]), Number(at[2]));

  const placeAt = text.match(/\/place\/[^/@]+\/@(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)/);
  if (placeAt) return valid(Number(placeAt[1]), Number(placeAt[2]));

  const dir = text.match(/\/dir\/[^/]+\/[^/]+\/@(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)/);
  if (dir) return valid(Number(dir[1]), Number(dir[2]));

  const q = text.match(/[?&]q=(?:loc:)?(-?\d+(?:\.\d+)?)(?:%2C|,\s*)(?:\+|%20|\s)*(-?\d+(?:\.\d+)?)/i);
  if (q) return valid(Number(q[1]), Number(q[2]));

  const query = text.match(/[?&]query=(-?\d+(?:\.\d+)?)(?:%2C|,\s*)(?:\+|%20|\s)*(-?\d+(?:\.\d+)?)/i);
  if (query) return valid(Number(query[1]), Number(query[2]));

  const ll = text.match(/[?&]ll=(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)/i);
  if (ll) return valid(Number(ll[1]), Number(ll[2]));

  const sll = text.match(/[?&]sll=(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)/i);
  if (sll) return valid(Number(sll[1]), Number(sll[2]));

  const daddr = text.match(/[?&]daddr=(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)/i);
  if (daddr) return valid(Number(daddr[1]), Number(daddr[2]));

  const center = text.match(/[?&]center=(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)/i);
  if (center) return valid(Number(center[1]), Number(center[2]));

  const markers = text.match(/[?&]markers=(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)/i);
  if (markers) return valid(Number(markers[1]), Number(markers[2]));

  const latlng = text.match(/[?&]latlng=(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)/i);
  if (latlng) return valid(Number(latlng[1]), Number(latlng[2]));

  const destination = text.match(/[?&]destination=(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)/i);
  if (destination) return valid(Number(destination[1]), Number(destination[2]));

  const jsonArr = text.match(/\[null,null,(-?\d+(?:\.\d+)?),\s*(-?\d+(?:\.\d+)?)\]/);
  if (jsonArr) return valid(Number(jsonArr[1]), Number(jsonArr[2]));

  const pair = text.match(PAIR);
  if (pair) return valid(Number(pair[1]), Number(pair[2]));

  return null;
}

/** "11.556400, 104.928200" at 6 decimal places. */
export function formatCoordinates(latitude?: number | null, longitude?: number | null): string {
  if (latitude == null || longitude == null) return '';
  return `${latitude.toFixed(6)}, ${longitude.toFixed(6)}`;
}

export function googleMapsUrl(latitude: number, longitude: number): string {
  const lat = encodeURIComponent(latitude);
  const lng = encodeURIComponent(longitude);
  return `https://maps.google.com/maps?q=${lat},${lng}&z=16`;
}
