import type { PageCatalog } from '../types';

export const paymentDetail: PageCatalog = {
  paymentDetails: ['Payment details', 'ព័ត៌មានលម្អិតការទូទាត់'],
  copied: ['Copied', 'បានចម្លង'],
  method: ['Method', 'វិធីសាស្ត្រ'],
  user: ['User', 'អ្នកប្រើប្រាស់'],
  owner: ['Owner', 'ម្ចាស់'],
  booking: ['Booking', 'ការកក់'],
  created: ['Created', 'បានបង្កើត'],
  refunded: ['Refunded', 'បានសងប្រាក់វិញ'],
  notSet: ['Not set', 'មិនបានកំណត់'],
  bookingDetails: ['Booking details', 'ព័ត៌មានលម្អិតការកក់'],
  back: ['Back', 'ត្រឡប់ក្រោយ'],
  waitingForPayment: ['Waiting for payment', 'កំពុងរង់ចាំការទូទាត់'],
  stripeWaitingHelp: [
    'Complete the card payment in the Stripe checkout window. This receipt updates automatically once Stripe confirms the transaction.',
    'សូមបញ្ចប់ការទូទាត់ដោយកាតនៅក្នុងផ្ទាំង Stripe Checkout។ បង្កាន់ដៃនេះនឹងធ្វើបច្ចុប្បន្នភាពដោយស្វ័យប្រវត្តិ នៅពេល Stripe បញ្ជាក់ប្រតិបត្តិការ។',
  ],
  abaWaitingHelp: [
    'Complete the payment on the ABA PayWay page. This receipt updates automatically once PayWay confirms the transaction.',
    'សូមបញ្ចប់ការទូទាត់នៅលើទំព័រ ABA PayWay។ បង្កាន់ដៃនេះនឹងធ្វើបច្ចុប្បន្នភាពដោយស្វ័យប្រវត្តិ នៅពេល PayWay បញ្ជាក់ប្រតិបត្តិការ។',
  ],
  checkStatus: ['Check status', 'ពិនិត្យស្ថានភាព'],
  checking: ['Checking…', 'កំពុងពិនិត្យ…'],
  refunds: ['Refunds', 'ការសងប្រាក់វិញ'],
  details: ['Details', 'ព័ត៌មានលម្អិត'],
  about: [
    'RentEasy Web — web platform edition of the RentEasy mobile app.',
    'RentEasy Web — កំណែវេទិកាគេហទំព័រនៃកម្មវិធីទូរស័ព្ទ RentEasy។',
  ],
  providerUnreachable: [
    'Could not reach the payment provider. Try again shortly.',
    'មិនអាចភ្ជាប់ទៅអ្នកផ្តល់សេវាទូទាត់បានទេ។ សូមព្យាយាមម្តងទៀតក្នុងពេលបន្តិច។',
  ],
  refundAlreadyPending: [
    'A refund request is already under review.',
    'សំណើសងប្រាក់កំពុងស្ថិតក្រោមការពិនិត្យរួចហើយ។',
  ],
  refundAlreadyProcessed: [
    'This payment has already been refunded.',
    'ការទូទាត់នេះត្រូវបានសងប្រាក់វិញរួចហើយ។',
  ],
  paymentNotRefundable: [
    'Only successful payments can be submitted for refund review.',
    'មានតែការទូទាត់ដែលជោគជ័យប៉ុណ្ណោះដែលអាចដាក់សំណើសងប្រាក់វិញបាន។',
  ],
  refundWindowClosed: [
    'Renter refund requests must be submitted within 7 days of payment.',
    'សំណើសងប្រាក់ពីអ្នកជួលត្រូវដាក់ក្នុងរយៈពេល ៧ ថ្ងៃបន្ទាប់ពីការទូទាត់។',
  ],
  refundSubmitFailed: [
    'Could not submit the refund request. Please try again.',
    'មិនអាចដាក់សំណើសងប្រាក់វិញបានទេ។ សូមព្យាយាមម្តងទៀត។',
  ],
};
