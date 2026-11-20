// Google Fonts (all SIL Open Font License). Add a font: import its loader and register it below.
import {loadFont as anton} from '@remotion/google-fonts/Anton';
import {loadFont as bebas} from '@remotion/google-fonts/BebasNeue';
import {loadFont as inter} from '@remotion/google-fonts/Inter';
import {loadFont as montserrat} from '@remotion/google-fonts/Montserrat';
import {loadFont as poppins} from '@remotion/google-fonts/Poppins';

const loaders: Record<string, () => {fontFamily: string}> = {
  Anton: () => anton('normal', {weights: ['400'], subsets: ['latin']}),
  'Bebas Neue': () => bebas('normal', {weights: ['400'], subsets: ['latin']}),
  Inter: () => inter('normal', {weights: ['400', '600', '800'], subsets: ['latin']}),
  Montserrat: () => montserrat('normal', {weights: ['600', '800', '900'], subsets: ['latin']}),
  Poppins: () => poppins('normal', {weights: ['600', '800'], subsets: ['latin']}),
};

const cache: Record<string, string> = {};

export const fontFamily = (name: string): string => {
  if (cache[name]) return cache[name];
  const loader = loaders[name];
  cache[name] = loader ? loader().fontFamily : name; // unknown names fall back to system font stack
  return cache[name];
};
