/**
 * Raw backend value -> Khmer label.
 *
 * English always falls back to the raw value itself (the backend already
 * returns an English string), so only the Khmer overlay lives here. Used by
 * `LanguageService.valueLabel()` in place of the per-component `khmer` maps
 * that used to be inlined in each source file.
 */
export const VALUE_KM: Readonly<Record<string, string>> = {
  // Booking statuses / tabs
  all: 'ទាំងអស់',
  All: 'ទាំងអស់',
  Pending: 'កំពុងរង់ចាំ',
  Approved: 'បានអនុម័ត',
  Confirmed: 'បានបញ្ជាក់',
  Rejected: 'បានបដិសេធ',
  Cancelled: 'បានលុបចោល',
  Expired: 'ផុតកំណត់',
  // Payment statuses
  Success: 'ជោគជ័យ',
  Successful: 'ជោគជ័យ',
  Failed: 'បរាជ័យ',
  Refunded: 'បានសងប្រាក់វិញ',
  Refunding: 'កំពុងសងប្រាក់វិញ',
  Refund: 'បានសងប្រាក់វិញ',
  'Refund failed': 'ការសងប្រាក់បរាជ័យ',
  Accepted: 'បានទទួល',
  'No Refund': 'មិនមានការសងប្រាក់ទេ',
  Processed: 'បានដំណើរការ',
  // Payout statuses
  Scheduled: 'បានកំណត់ពេល',
  Eligible: 'ត្រៀមផ្ទេរ',
  Paid: 'បានផ្ទេរ',
  // Sessions / audit
  Active: 'សកម្ម',
  Inactive: 'មិនសកម្ម',
  Login: 'ចូលប្រើ',
  Logout: 'ចាកចេញ',
  Create: 'បង្កើត',
  Update: 'កែប្រែ',
  Delete: 'លុប',
  'Status change': 'ផ្លាស់ប្តូរស្ថានភាព',
  Payment: 'ការទូទាត់',
  Payout: 'ការផ្ទេរប្រាក់',
  Email: 'អ៊ីមែល',
  Google: 'Google',
  Telegram: 'Telegram',
  Desktop: 'កុំព្យូទ័រ',
  Mobile: 'ទូរស័ព្ទ',
  Tablet: 'Tablet',
  Bot: 'Bot',
  Unknown: 'មិនដឹង',
  // Roles
  Renter: 'អ្នកជួល',
  'Property Owner': 'ម្ចាស់អចលនទ្រព្យ',
  'Super Admin': 'អ្នកគ្រប់គ្រងកំពូល',
};

export const MONTHS_EN: readonly string[] = [
  'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
];

export const MONTHS_KM: readonly string[] = [
  'មករា', 'កុម្ភៈ', 'មីនា', 'មេសា', 'ឧសភា', 'មិថុនា', 'កក្កដា', 'សីហា', 'កញ្ញា', 'តុលា', 'វិច្ឆិកា', 'ធ្នូ',
];
