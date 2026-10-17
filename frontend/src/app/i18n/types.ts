export type SiteLanguage = 'en' | 'km';

export type TranslationEntry = readonly [en: string, km: string];

export type PageCatalog = Readonly<Record<string, TranslationEntry>>;

export type Catalog = Readonly<Record<string, TranslationEntry>>;
