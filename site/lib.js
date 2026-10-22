const LIST_KEYS = ['bowlers', 'batters', 'death_bowlers', 'records'];
import { NEUTRAL_TEAM_COLOUR, TEAM_COLOURS, teamColour } from './teams.js';

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

export function teamChipsForSeason(data, season) {
  const allTeams = teamsForSeason(data, 'All');
  const playingTeams = new Set(teamsForSeason(data, season));
  const isAllSeasons = scopeKey(season) === 'All';
  return allTeams.map((team) => ({
    team,
    disabled: !isAllSeasons && !playingTeams.has(team),
  }));
}

export function runRateSeasonChoices(data, team) {
  const seasons = Array.isArray(data?.seasons) ? data.seasons.map(String) : [];
  const teamKey = scopeKey(team);
  const leagueRows = Array.isArray(data?.run_rate_by_season?.All) ? data.run_rate_by_season.All : [];
  const teamRows = teamKey === 'All'
    ? leagueRows
    : Array.isArray(data?.run_rate_by_season?.[teamKey]) ? data.run_rate_by_season[teamKey] : [];
  const bySeason = (rows) => new Map(rows.map((row) => [String(row.season_year), row]));
  const teamBySeason = bySeason(teamRows);
  const leagueBySeason = bySeason(leagueRows);
  return seasons.map((season) => {
    const teamRow = teamBySeason.get(season);
    const row = teamRow || (teamKey === 'All' ? undefined : leagueBySeason.get(season));
    return { season, row, teamPlayed: teamKey === 'All' || Boolean(teamRow) };
  }).filter(({ row }) => row && Number.isFinite(Number(row.run_rate)));
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
  return new Intl.NumberFormat(undefined, {
    minimumFractionDigits: maximumFractionDigits,
    maximumFractionDigits,
  }).format(number);
}

export function formatCount(value) {
  return formatNumber(value, 0);
}

export function formatPercent(value) {
  const formatted = formatNumber(value, 2);
  return formatted === '—' ? formatted : `${formatted}%`;
}

function relativeLuminance(hex) {
  const match = /^#?([\da-f]{3}|[\da-f]{6})$/i.exec(String(hex ?? ''));
  if (!match) return Number.NaN;
  const source = match[1].length === 3
    ? [...match[1]].map((digit) => `${digit}${digit}`).join('')
    : match[1];
  const channels = [0, 2, 4].map((offset) => Number.parseInt(source.slice(offset, offset + 2), 16) / 255);
  const linear = channels.map((channel) => (
    channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4
  ));
  return (0.2126 * linear[0]) + (0.7152 * linear[1]) + (0.0722 * linear[2]);
}

export function contrastRatio(first, second) {
  const firstLuminance = relativeLuminance(first);
  const secondLuminance = relativeLuminance(second);
  if (!Number.isFinite(firstLuminance) || !Number.isFinite(secondLuminance)) return 0;
  const lighter = Math.max(firstLuminance, secondLuminance);
  const darker = Math.min(firstLuminance, secondLuminance);
  return (lighter + 0.05) / (darker + 0.05);
}

export function buildHeadline(data, season, team) {
  const seasonKey = scopeKey(season);
  const teamKey = scopeKey(team);
  const leagueRows = data?.run_rate_by_season?.All;
  const fallback = 'IPL scoring by season';
  const rowForSeason = (rows, year) => Array.isArray(rows)
    ? rows.find((row) => String(row.season_year) === String(year))
    : undefined;
  const hasRate = (row) => row && Number.isFinite(Number(row.run_rate));

  if (teamKey !== 'All') {
    const teamRows = data?.run_rate_by_season?.[teamKey];
    if (!Array.isArray(teamRows) || !teamRows.length) return fallback;
    if (seasonKey !== 'All') {
      const row = rowForSeason(teamRows, seasonKey);
      if (!hasRate(row)) return fallback;
      return `${teamKey} scored at ${formatNumber(row.run_rate)} runs an over in ${seasonKey}.`;
    }
    const ordered = teamRows
      .filter(hasRate)
      .slice()
      .sort((first, second) => Number(first.season_year) - Number(second.season_year));
    if (!ordered.length) return fallback;
    const first = ordered[0];
    const last = ordered[ordered.length - 1];
    if (first === last) {
      return `${teamKey} scored at ${formatNumber(first.run_rate)} runs an over in ${first.season_year}.`;
    }
    return `${teamKey} moved from ${formatNumber(first.run_rate)} runs an over in ${first.season_year} to ${formatNumber(last.run_rate)} in ${last.season_year}.`;
  }

  if (!Array.isArray(leagueRows) || !leagueRows.length) return fallback;
  if (seasonKey !== 'All') {
    const row = rowForSeason(leagueRows, seasonKey);
    if (!hasRate(row)) return fallback;
    return `The league scored at ${formatNumber(row.run_rate)} runs an over in ${seasonKey}.`;
  }

  const orderedBySeason = leagueRows
    .filter(hasRate)
    .slice()
    .sort((first, second) => Number(first.season_year) - Number(second.season_year));
  if (!orderedBySeason.length) return fallback;
  const earliest = orderedBySeason[0];
  const latest = orderedBySeason[orderedBySeason.length - 1];
  if (earliest === latest) {
    return `League scoring was ${formatNumber(earliest.run_rate)} runs an over in ${earliest.season_year}.`;
  }
  return `Scoring has risen from ${formatNumber(earliest.run_rate)} runs an over in ${earliest.season_year} to ${formatNumber(latest.run_rate)} in ${latest.season_year}.`;
}

export { NEUTRAL_TEAM_COLOUR, TEAM_COLOURS, teamColour };
