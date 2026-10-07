/** UI helpers ported from backend/core/templatetags/ui.py + core/i18n.py. */

export function bookingPill(status: string): string {
  switch (status) {
    case 'Pending':
      return 'pill-pending';
    case 'Approved':
      return 'pill-approved';
    case 'Rejected':
      return 'pill-rejected';
    case 'Cancelled':
      return 'pill-cancelled';
    default:
      return 'pill-neutral';
  }
}

export function rolePill(role: string): string {
  if (role === 'superadmin') return 'pill-approved';
  if (role === 'owner') return 'pill-neutral';
  return 'pill-cancelled';
}

export function roleLabel(role: string): string {
  switch (role) {
    case 'superadmin':
      return 'Super Admin';
    case 'owner':
      return 'Property Owner';
    case 'renter':
      return 'Renter';
    default:
      return role;
  }
}

/** Payment status pill: refund state wins over success/failure. */
export function paymentPill(status: string, refundStatus?: string): string {
  if (refundStatus === 'Processed') return 'pill-refunded';
  if (status === 'Success') return 'pill-approved';
  if (status === 'Failed') return 'pill-rejected';
  return 'pill-neutral';
}

export function paymentStatusLabel(status: string): string {
  return status === 'Success' ? 'Successful' : status === 'Failed' ? 'Failed' : status;
}

export function refundPill(status: string): string {
  if (status === 'Processed') return 'pill-refunded';
  if (status === 'Pending') return 'pill-pending';
  return 'pill-neutral';
}

export function refundStatusLabel(status: string): string {
  return status === 'None' ? 'No Refund' : status;
}

export function refundReasonLabel(reason: string): string {
  switch (reason) {
    case 'cancelled_by_renter':
      return 'Cancelled by renter';
    case 'rejected_by_owner':
      return 'Rejected by owner';
    default:
      return 'Other';
  }
}

/** Icon name used next to a payment method. */
export function methodIcon(method: string): string {
  if (method.startsWith('Wing')) return 'send';
  if (method.startsWith('Credit')) return 'card';
  return 'layers';
}

export function methodLabel(method: string): string {
  return method.replace(' (Mock)', '');
}

/** Format a number as `$1,234` (mirrors the Django `usd` filter). */
export function usd(value: number | null | undefined, decimals = 0): string {
  const n = Number(value || 0);
  if (decimals === 0) return `$${Math.round(n).toLocaleString('en-US')}`;
  return `$${n.toLocaleString('en-US', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  })}`;
}

/** `dd/MM/yyyy` (mirrors the Django `short_date` filter). */
export function shortDate(value: string | null | undefined): string {
  if (!value) return '';
  const d = new Date(value);
  if (isNaN(d.getTime())) return String(value);
  const p = (n: number) => String(n).padStart(2, '0');
  return `${p(d.getDate())}/${p(d.getMonth() + 1)}/${d.getFullYear()}`;
}

/** `dd MMM yyyy, hh:mm AM/PM` (mirrors the Django `pretty_date` filter). */
export function prettyDate(value: string | null | undefined): string {
  if (!value) return '';
  const d = new Date(value);
  if (isNaN(d.getTime())) return String(value);
  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const h24 = d.getHours();
  const suffix = h24 >= 12 ? 'PM' : 'AM';
  let h = h24 % 12;
  if (h === 0) h = 12;
  const m = String(d.getMinutes()).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${day} ${months[d.getMonth()]} ${d.getFullYear()}, ${h}:${m} ${suffix}`;
}

/** Initials for avatar circles (first two significant words). */
export function initials(name?: string | null): string {
  if (!name) return '?';
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return '?';
  if (parts.length === 1) return parts[0].substring(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}
