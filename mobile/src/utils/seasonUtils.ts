export type Hemisphere = 'north' | 'south';
export type Season    = 'spring' | 'summer' | 'autumn' | 'winter';

const NORTH_BY_MONTH: Season[] = [
  'winter','winter','spring',   // Jan Feb Mar
  'spring','spring','summer',   // Apr May Jun
  'summer','summer','autumn',   // Jul Aug Sep
  'autumn','autumn','winter',   // Oct Nov Dec
];

const OPPOSITE: Record<Season, Season> = {
  spring: 'autumn', summer: 'winter',
  autumn: 'spring', winter: 'summer',
};

export function getCurrentSeason(hemisphere: Hemisphere = 'north'): Season {
  const s = NORTH_BY_MONTH[new Date().getMonth()];
  return hemisphere === 'north' ? s : OPPOSITE[s];
}

/**
 * Multiplier applied to the base watering interval (days).
 *  < 1.0 → shorter interval → water MORE often (summer heat)
 *  > 1.0 → longer  interval → water LESS often (winter dormancy)
 */
export function getSeasonalMultiplier(hemisphere: Hemisphere = 'north'): number {
  switch (getCurrentSeason(hemisphere)) {
    case 'summer': return 0.75;
    case 'spring': return 0.90;
    case 'autumn': return 1.20;
    case 'winter': return 1.50;
  }
}

export const SEASON_EMOJI: Record<Season, string> = {
  spring: '🌸', summer: '☀️', autumn: '🍂', winter: '❄️',
};

export interface SeasonBannerInfo {
  season: Season;
  emoji:  string;
  label:  string;
  mult:   number;
  note:   string;
}

export function getSeasonBannerInfo(hemisphere: Hemisphere = 'north'): SeasonBannerInfo {
  const season = getCurrentSeason(hemisphere);
  const mult   = getSeasonalMultiplier(hemisphere);
  const emoji  = SEASON_EMOJI[season];
  const label  = season.charAt(0).toUpperCase() + season.slice(1);

  let note: string;
  if (mult < 1) {
    note = `${emoji} ${label} — watering adjusted ${Math.round((1 - mult) * 100)}% more often than your base rate.`;
  } else if (mult > 1) {
    note = `${emoji} ${label} — watering stretched ${Math.round((mult - 1) * 100)}% longer; plants rest in ${season}.`;
  } else {
    note = `${emoji} ${label} — care schedules running at normal frequency.`;
  }

  return { season, emoji, label, mult, note };
}
