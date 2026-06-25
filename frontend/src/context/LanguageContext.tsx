import {
  createContext,
  useContext,
  useState,
  useCallback,
  useMemo,
  type ReactNode,
} from 'react';
import { translations, LANGUAGES } from '../i18n';
import type { Language, TranslationKeys } from '../i18n';

interface LanguageContextType {
  language: Language;
  setLanguage: (lang: Language) => void;
  t: TranslationKeys;
  languages: typeof LANGUAGES;
}

const LanguageContext = createContext<LanguageContextType | null>(null);

const STORAGE_KEY = 'smartwifi_language';

function getInitialLanguage(): Language {
  try {
    const stored = localStorage.getItem(STORAGE_KEY) as Language | null;
    if (stored && translations[stored]) return stored;
  } catch {
    // ignore
  }
  // Auto-detect from browser
  const browserLang = navigator.language.slice(0, 2).toLowerCase();
  const supported: Language[] = ['uz', 'en', 'ru', 'es', 'zh'];
  return supported.includes(browserLang as Language) ? (browserLang as Language) : 'uz';
}

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [language, setLanguageState] = useState<Language>(getInitialLanguage);

  const setLanguage = useCallback((lang: Language) => {
    setLanguageState(lang);
    try {
      localStorage.setItem(STORAGE_KEY, lang);
    } catch {
      // ignore
    }
  }, []);

  const value = useMemo<LanguageContextType>(() => ({
    language,
    setLanguage,
    t: translations[language],
    languages: LANGUAGES,
  }), [language, setLanguage]);

  return (
    <LanguageContext.Provider value={value}>
      {children}
    </LanguageContext.Provider>
  );
}

export function useLanguage(): LanguageContextType {
  const ctx = useContext(LanguageContext);
  if (!ctx) throw new Error('useLanguage must be used within LanguageProvider');
  return ctx;
}
