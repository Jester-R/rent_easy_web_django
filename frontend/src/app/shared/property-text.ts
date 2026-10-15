import type { Property } from '../models';
import type { SiteLanguage } from '../i18n/types';

function pick(english: string | undefined | null, khmer: string | undefined | null, language: SiteLanguage): string {
  const en = (english ?? '').trim();
  const km = (khmer ?? '').trim();
  if (language === 'km') return km || en;
  return en || km;
}

export function propertyTitle(property: Property | null | undefined, language: SiteLanguage): string {
  if (!property) return '';
  return pick(property.title, property.title_km, language);
}

export function propertyLocation(property: Property | null | undefined, language: SiteLanguage): string {
  if (!property) return '';
  return pick(property.location, property.location_km, language);
}

export function propertyDescription(property: Property | null | undefined, language: SiteLanguage): string {
  if (!property) return '';
  return pick(property.description, property.description_km, language);
}
