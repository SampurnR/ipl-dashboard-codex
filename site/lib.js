const LIST_KEYS = ['bowlers', 'batters', 'death_bowlers', 'records'];

function scopeKey(value) {
  return value === null || value === undefined || value === '' ? 'All' : String(value);
}

export function teamsForSeason(data, season) {
  if (scopeKey(season) === 'All') {
    return Array.isArray(data?.teams) ? data.teams : [];
  }
  const teams = data?.teams_by_season?.[scopeKey(season)];
  return Array.isArray(teams) ? teams : [];
}

export function normalizeTeamForSeason(data, season, team) {
  const teamKey = scopeKey(team);
  if (teamKey === 'All') return 'All';
  return teamsForSeason(data, season).includes(teamKey) ? teamKey : 'All';
}

export function resolveScope(data, season, team) {
  const empty = Object.fromEntries(LIST_KEYS.map((key) => [key, []]));
  const selected = data?.scopes?.[scopeKey(season)]?.[scopeKey(team)];
  if (!selected || typeof selected !== 'object') return empty;
  return Object.fromEntries(LIST_KEYS.map((key) => [
    key,
    Array.isArray(selected[key]) ? selected[key] : [],
  ]));
}

export function thresholdFor(data, season) {
  const thresholdKey = scopeKey(season) === 'All' ? 'all_seasons' : 'single_season';
  const threshold = Number(data?.thresholds?.[thresholdKey]);
  return Number.isFinite(threshold) ? threshold : 0;
}

export function emptyMessage(kind, season, data) {
  const threshold = thresholdFor(data, season);
  if (kind === 'batters') {
    return `No batter with at least ${threshold} balls faced qualifies in this selection.`;
  }
  if (kind === 'death_bowlers') {
    return `No death-over bowler has bowled at least ${threshold} legal balls in this selection.`;
  }
  if (kind === 'bowlers') {
    return `No bowler has bowled at least ${threshold} legal balls in this selection.`;
  }
  return 'No records are available for this selection.';
}

export function formatNumber(value, maximumFractionDigits = 2) {
  const number = Number(value);
  if (!Number.isFinite(number)) return '—';
  return new Intl.NumberFormat(undefined, { maximumFractionDigits }).format(number);
}

export function formatCount(value) {
  return formatNumber(value, 0);
}

export function formatPercent(value) {
  const formatted = formatNumber(value, 2);
  return formatted === '—' ? formatted : `${formatted}%`;
}
