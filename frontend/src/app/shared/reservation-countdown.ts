/** Format a booking reservation deadline as a live HH:MM:SS countdown. */
export function formatReservationCountdown(
  value: string | null | undefined,
  now: number = Date.now(),
): string | null {
  if (!value) return null;
  const expiresAt = Date.parse(value);
  if (!Number.isFinite(expiresAt)) return null;

  const totalSeconds = Math.max(0, Math.ceil((expiresAt - now) / 1000));
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  const pad = (part: number) => String(part).padStart(2, '0');
  return `${pad(hours)}:${pad(minutes)}:${pad(seconds)}`;
}
