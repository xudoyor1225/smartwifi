export { LANGUAGES } from './translations';
export type { Language, TranslationKeys } from './translations';
import uz from './uz';
import en from './en';
import ru from './ru';
import es from './es';
import zh from './zh';
import type { Language, TranslationKeys } from './translations';

export const translations: Record<Language, TranslationKeys> = { uz, en, ru, es, zh };
