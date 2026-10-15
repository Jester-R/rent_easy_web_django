/** Notification title/body translations, mirrored from backend/core/i18n.py. */

type Template = readonly [string, string];

export const NOTIFICATION_TEXT: Readonly<Record<string, Template>> = {
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
    'The booking for {title} was cancelled. Any refund request is waiting for administrator review.',
    'ការកក់សម្រាប់ {title} ត្រូវបានបោះបង់។ សំណើសងប្រាក់កំពុងរង់ចាំអ្នកគ្រប់គ្រងពិនិត្យ។',
  ],
  notif_booking_rejected: ['Booking rejected', 'ការកក់ត្រូវបានបដិសេធ'],
  notif_booking_rejected_body: ['Your booking for {title} was rejected.', 'ការកក់សម្រាប់ {title} ត្រូវបានបដិសេធ។'],
  notif_refund_processed: ['Refund processed', 'សងវិញទឹកប្រាក់ត្រូវបានដំណើរការ'],
  notif_refund_processed_body: ['{amount} was refunded for {title}', '{amount} ត្រូវបានសងវិញសម្រាប់ {title}'],
  notif_refund_requested: ['Refund needs review', 'សំណើសងប្រាក់ត្រូវការការពិនិត្យ'],
  notif_refund_requested_body: ['Refund {reference} for {title} ({amount}) is waiting for administrator review.', 'សំណើសងប្រាក់ {reference} សម្រាប់ {title} ចំនួន {amount} កំពុងរង់ចាំអ្នកគ្រប់គ្រងពិនិត្យ។'],
  notif_refund_rejected: ['Refund request reviewed', 'សំណើសងប្រាក់ត្រូវបានពិនិត្យ'],
  notif_refund_rejected_body: ['Refund request {reference} for {title} was rejected. Review the note on the payment details.', 'សំណើសងប្រាក់ {reference} សម្រាប់ {title} ត្រូវបានបដិសេធ។ សូមពិនិត្យមើលកំណត់ត្រានៅព័ត៌មានការទូទាត់។'],
  notif_payout_paid: ['Rent payout sent', 'ប្រាក់ជួលត្រូវបានផ្ទេរ'],
  notif_payout_paid_body: [
    '{amount} for {title} was sent to your payout account.',
    '{amount} សម្រាប់ {title} ត្រូវបានផ្ទេរទៅគណនីទទួលប្រាក់របស់អ្នក។',
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
  const overrides = notification.params?.['message_overrides'] as
    | { title_en?: string; title_km?: string; body_en?: string; body_km?: string }
    | undefined;
  const title = (language === 'km' ? overrides?.title_km : overrides?.title_en)
    || NOTIFICATION_TEXT[notification.title_key]?.[index]
    || notification.title_key;
  const body = (language === 'km' ? overrides?.body_km : overrides?.body_en)
    || NOTIFICATION_TEXT[notification.body_key]?.[index]
    || notification.body_key;
  return {
    title: interpolate(title, notification.params),
    body: interpolate(body, notification.params),
  };
}
