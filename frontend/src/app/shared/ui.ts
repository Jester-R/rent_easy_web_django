/** UI helpers ported from backend/core/templatetags/ui.py + core/i18n.py. */

export function bookingPill(status: string): string {
  switch (status) {
    case 'Pending':
      return 'pill-pending';
    case 'Approved':
    case 'Confirmed':
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

/** Canonical payment methods (shared by every payment modal). */
export const PAYMENT_METHODS: readonly string[] = [
  'ABA Pay (Mock)',
  'Wing (Mock)',
  'Credit Card (Mock)',
];

export interface CategoryOption {
  value: string;
  label: string;
}

/** Property categories (mirrors listings.models.PropertyCategory). */
export const PROPERTY_CATEGORIES: readonly CategoryOption[] = [
  { value: 'apartment', label: 'Apartment' },
  { value: 'house', label: 'House' },
  { value: 'condo', label: 'Condo' },
  { value: 'villa', label: 'Villa' },
  { value: 'room', label: 'Room' },
  { value: 'studio', label: 'Studio' },
  { value: 'office', label: 'Office' },
  { value: 'land', label: 'Land' },
];

export function categoryLabel(value?: string | null): string {
  if (!value) return '';
  return PROPERTY_CATEGORIES.find((c) => c.value === value)?.label ?? value;
}

type Template = readonly [string, string];

/** Notification title/body translations, mirrored from backend/core/i18n.py. */
const NOTIFICATION_TEXT: Record<string, Template> = {
  notif_new_request: ['New booking request', 'សំណើកក់ថ្មី'],
  notif_new_request_body: ['{renter} requested {title}', '{renter} បានស្នើសុំ {title}'],
  notif_booking_update: ['Booking updated', 'ការកក់ត្រូវបានធ្វើបច្ចុប្បន្នភាព'],
  notif_booking_update_body: [
    'Your booking for {title} is now {status}',
    'ការកក់របស់អ្នកសម្រាប់ {title} ឥឡូវនេះជា {status}',
  ],
  notif_payment_received: ['Payment received', 'ទទួលបានការទូទាត់'],
  notif_payment_received_body: [
    '{renter} paid {amount} for {title}',
    '{renter} បានបង់ {amount} សម្រាប់ {title}',
  ],
  notif_booking_approved: ['Booking approved', 'ការកក់ត្រូវបានអនុម័ត'],
  notif_booking_approved_body: [
    'Your booking for {title} was approved. Complete payment now.',
    'ការកក់របស់អ្នកសម្រាប់ {title} ត្រូវបានអនុម័ត។ បង់ការទូទាត់ឥឡូវនេះ។',
  ],
  notif_booking_approved_paid: [
    'Your booking for {title} was approved and payment confirmed.',
    'ការកក់របស់អ្នកសម្រាប់ {title} ត្រូវបានអនុម័ត និងការទូទាត់ត្រូវបានបញ្ជាក់។',
  ],
  notif_renter_confirmed: ['Renter confirmed', 'អ្នកជួលបានបញ្ជាក់'],
  notif_renter_confirmed_body: [
    '{renter} confirmed the booking for {title}',
    '{renter} បានបញ្ជាក់ការកក់សម្រាប់ {title}',
  ],
  notif_owner_request: ['New owner request', 'សំណើម្ចាស់ថ្មី'],
  notif_owner_request_body: [
    '{name} ({email}) requested a property owner account.',
    '{name} ({email}) បានស្នើសុំគណនីម្ចាស់អចលនទ្រព្យ។',
  ],
  notif_owner_approved: ['Owner account approved', 'គណនីម្ចាស់ត្រូវបានអនុម័ត'],
  notif_owner_approved_body: [
    'Your property owner account was approved. You can now log in.',
    'គណនីម្ចាស់អចលនទ្រព្យរបស់អ្នកត្រូវបានអនុម័ត។ អ្នកអាចចូលគណនីបានហើយ។',
  ],
  notif_owner_rejected: ['Owner request declined', 'សំណើម្ចាស់ត្រូវបានបដិសេធ'],
  notif_owner_rejected_body: [
    'Your property owner account request was declined.',
    'សំណើគណនីម្ចាស់អចលនទ្រព្យរបស់អ្នកត្រូវបានបដិសេធ។',
  ],
  notif_booking_cancelled: ['Booking cancelled', 'ការកក់ត្រូវបានបោះបង់'],
  notif_booking_cancelled_body: [
    'The booking for {title} was cancelled and eligible for refund.',
    'ការកក់សម្រាប់ {title} ត្រូវបានបោះបង់ និងមានសិទ្ធិសងវិញទឹកប្រាក់។',
  ],
  notif_booking_rejected: ['Booking rejected', 'ការកក់ត្រូវបានបដិសេធ'],
  notif_booking_rejected_body: [
    'Your booking for {title} was rejected.',
    'ការកក់របស់អ្នកសម្រាប់ {title} ត្រូវបានបដិសេធ។',
  ],
  notif_refund_processed: ['Refund processed', 'សងវិញទឹកប្រាក់ត្រូវបានដំណើរការ'],
  notif_refund_processed_body: [
    '{amount} was refunded for {title}',
    '{amount} ត្រូវបានសងវិញសម្រាប់ {title}',
  ],
};

function interpolate(template: string, params?: Record<string, unknown>): string {
  return template.replace(/\{(\w+)\}/g, (_match, key: string) => {
    const value = params?.[key];
    return value === undefined || value === null ? '' : String(value);
  });
}

/** Render a notification's i18n keys + params into display text. */
export function notificationText(
  notification: { title_key: string; body_key: string; params?: Record<string, unknown> },
  language: 'en' | 'km' = 'en'
): { title: string; body: string } {
  const index = language === 'km' ? 1 : 0;
  const title = NOTIFICATION_TEXT[notification.title_key]?.[index] ?? notification.title_key;
  const body = NOTIFICATION_TEXT[notification.body_key]?.[index] ?? notification.body_key;
  return {
    title: interpolate(title, notification.params),
    body: interpolate(body, notification.params),
  };
}
