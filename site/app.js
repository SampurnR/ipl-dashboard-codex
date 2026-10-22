import {
  buildHeadline,
  emptyMessage,
  formatCount,
  formatNumber,
  formatPercent,
  normalizeTeamForSeason,
  resolveScope,
  runRateSeasonChoices,
  teamChipsForSeason,
  teamsForSeason,
} from './lib.js';
import { teamColour } from './teams.js';

const $ = (selector) => document.querySelector(selector);
const html = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
}[char]));
const number = (value) => Number.isFinite(Number(value)) ? Number(value) : 0;

const state = { data: null, season: 'All', team: 'All', renderCount: 0 };

function fmtDate(value) {
  const date = new Date(`${value}T00:00:00Z`);
  if (Number.isNaN(date.getTime())) return String(value ?? '');
  return new Intl.DateTimeFormat(undefined, {
    day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC',
  }).format(date);
}

function currentRunRateRows(team) {
  const rows = state.data?.run_rate_by_season?.[team === 'All' ? 'All' : team];
  return Array.isArray(rows) ? rows : [];
}

function runRateChart() {
  const seasons = Array.isArray(state.data.seasons) ? state.data.seasons.map(String) : [];
  const primaryName = state.team === 'All' ? 'All' : state.team;
  const primary = currentRunRateRows(primaryName);
  const league = state.team === 'All' ? [] : currentRunRateRows('All');
  const bySeason = (rows) => new Map(rows.map((row) => [String(row.season_year), row]));
  const primaryMap = bySeason(primary);
  const leagueMap = bySeason(league);
  const seasonChoices = runRateSeasonChoices(state.data, state.team);
  const points = seasons
    .map((season) => ({ season, row: primaryMap.get(season) }))
    .filter(({ row }) => row && Number.isFinite(Number(row.run_rate)));
  if (!points.length) return '<p class="empty-note">Run-rate data is not available for this selection.</p>';

  const comparison = seasons
    .map((season) => ({ season, row: leagueMap.get(season) }))
    .filter(({ row }) => row && Number.isFinite(Number(row.run_rate)));
  const allValues = [...points, ...comparison].map(({ row }) => Number(row.run_rate));
  const lowValue = Math.floor(Math.min(...allValues));
  const highValue = Math.ceil(Math.max(...allValues));
  const rawSpan = Math.max(1, highValue - lowValue);
  const step = rawSpan <= 2 ? 0.5 : rawSpan <= 5 ? 1 : 2;
  const tickStart = Math.floor((Math.min(...allValues) - step * 0.45) / step) * step;
  const tickEnd = Math.ceil((Math.max(...allValues) + step * 0.45) / step) * step;
  const ticks = [];
  for (let tick = tickStart; tick <= tickEnd + step * 0.1; tick += step) ticks.push(tick);
  if (ticks.length < 4) {
    const extra = (4 - ticks.length) / 2;
    for (let i = 0; i < Math.ceil(extra); i += 1) ticks.unshift(ticks[0] - step);
    while (ticks.length < 4) ticks.push(ticks[ticks.length - 1] + step);
  }

  const width = 1120;
  const height = 440;
  const left = 76;
  const right = 28;
  const top = 36;
  const bottom = 74;
  const plotWidth = width - left - right;
  const plotHeight = height - top - bottom;
  const minY = ticks[0];
  const maxY = ticks[ticks.length - 1];
  const xFor = (index) => left + (seasons.length <= 1 ? plotWidth / 2 : (index / (seasons.length - 1)) * plotWidth);
  const yFor = (value) => top + ((maxY - value) / (maxY - minY)) * plotHeight;
  const seasonIndex = new Map(seasons.map((season, index) => [season, index]));
  const primaryCoords = points.map(({ season, row }) => ({
    season, value: Number(row.run_rate), x: xFor(seasonIndex.get(season)), y: yFor(Number(row.run_rate)),
  }));
  const comparisonCoords = comparison.map(({ season, row }) => ({
    season, value: Number(row.run_rate), x: xFor(seasonIndex.get(season)), y: yFor(Number(row.run_rate)),
  }));
  const pathFor = (coords) => coords.map((point, index) => {
    const previous = coords[index - 1];
    const startsSegment = !previous || seasonIndex.get(point.season) > seasonIndex.get(previous.season) + 1;
    return `${startsSegment ? 'M' : 'L'} ${point.x.toFixed(1)} ${point.y.toFixed(1)}`;
  }).join(' ');
  const chosenIndex = seasonIndex.get(state.season);
  const markerX = chosenIndex === undefined ? null : xFor(chosenIndex);
  const extrema = new Set();
  extrema.add(primaryCoords[0].season);
  extrema.add(primaryCoords[primaryCoords.length - 1].season);
  extrema.add(primaryCoords.reduce((best, point) => point.value < best.value ? point : best).season);
  extrema.add(primaryCoords.reduce((best, point) => point.value > best.value ? point : best).season);

  const yAxis = ticks.map((tick) => {
    const y = yFor(tick);
    return `<g aria-hidden="true"><line class="chart-gridline" x1="${left}" y1="${y}" x2="${width - right}" y2="${y}"/><text class="chart-tick" x="${left - 13}" y="${y + 5}" text-anchor="end">${formatNumber(tick)}</text></g>`;
  }).join('');
  const xAxis = seasons.map((season, index) => `<text class="season-label${season === state.season ? ' is-selected' : ''}" x="${xFor(index)}" y="${height - 37}" text-anchor="middle">${html(season)}</text>`).join('');
  const marker = markerX === null ? '' : `<line class="season-marker" x1="${markerX}" y1="${top - 8}" x2="${markerX}" y2="${top + plotHeight + 10}" aria-hidden="true"/>`;
  const compareLine = comparisonCoords.length > 1
    ? `<path class="run-line league-line" d="${pathFor(comparisonCoords)}"><title>League run rate for comparison</title></path>`
    : '';
  const labels = primaryCoords.filter((point) => extrema.has(point.season)).map((point, index) => {
    const anchor = point.x < left + 48 ? 'start' : point.x > width - right - 48 ? 'end' : 'middle';
    const offset = index % 2 === 0 ? -15 : 23;
    return `<text class="point-value-label" x="${point.x}" y="${point.y + offset}" text-anchor="${anchor}">${formatNumber(point.value)}</text>`;
  }).join('');
  const pointButtons = seasonChoices.map(({ season, row, teamPlayed }) => {
    const point = {
      season,
      value: Number(row.run_rate),
      x: xFor(seasonIndex.get(season)),
      y: yFor(Number(row.run_rate)),
      teamPlayed,
    };
    const selected = point.season === state.season;
    const absentTeam = state.team !== 'All' && !point.teamPlayed;
    const label = absentTeam
      ? `${point.season}, ${state.team} did not play; league rate ${formatNumber(point.value)} runs per over${selected ? ', selected' : ''}`
      : `${point.season}, ${formatNumber(point.value)} runs per over${selected ? ', selected' : ''}`;
    return `<g class="season-point${selected ? ' is-selected' : ''}${absentTeam ? ' is-unplayed' : ''}" data-season="${point.season}" role="button" tabindex="${selected || state.season === 'All' && point.season === seasons[0] ? '0' : '-1'}" aria-label="${html(label)}" aria-pressed="${selected ? 'true' : 'false'}"><circle class="point-hit-area" cx="${point.x}" cy="${point.y}" r="15"/><circle class="point-mark${selected ? ' selected-mark' : ''}" cx="${point.x}" cy="${point.y}" r="${absentTeam ? 4.5 : 6}"><title>${html(label)}</title></circle></g>`;
  }).join('');
  const yLabel = '<text class="axis-title" transform="translate(19 225) rotate(-90)" text-anchor="middle">Runs per over</text>';
  const compareLegend = comparisonCoords.length
    ? '<p class="chart-legend"><span class="legend-line legend-team"></span>Selected team <span class="legend-line legend-league"></span>League</p>'
    : '';
  return `${compareLegend}<div class="timeline-scroll"><svg class="run-chart" viewBox="0 0 ${width} ${height}" role="group" aria-label="Run rate by season. Use left and right arrow keys to choose a season."><title>Run rate by season</title><desc>Each point is a season run rate. The vertical yellow line marks the selected season.</desc>${yAxis}${marker}${compareLine}<path class="run-line team-line" d="${pathFor(primaryCoords)}"><title>${html(state.team === 'All' ? 'League' : state.team)} run rate</title></path><line class="chart-axis" x1="${left}" y1="${top + plotHeight}" x2="${width - right}" y2="${top + plotHeight}"/>${xAxis}${yLabel}${labels}${pointButtons}</svg></div>`;
}

function teamChipMarkup() {
  const chips = teamChipsForSeason(state.data, state.season);
  const all = `<button type="button" class="team-chip all-chip${state.team === 'All' ? ' is-active' : ''}" data-team="All" aria-pressed="${state.team === 'All'}">All teams</button>`;
  return all + chips.map(({ team, disabled }) => {
    const accessible = disabled ? `${team}, did not play in ${state.season}` : team;
    return `<button type="button" class="team-chip${state.team === team ? ' is-active' : ''}" data-team="${html(team)}" ${disabled ? 'disabled' : ''} aria-label="${html(accessible)}" aria-pressed="${state.team === team}"><span class="chip-stripe" style="--team-colour:${teamColour(team)}" aria-hidden="true"></span>${html(team)}</button>`;
  }).join('');
}

function resultsStrip(record, large = false) {
  const counts = [
    { key: 'wins', label: 'Wins', short: 'W', value: number(record?.wins) },
    { key: 'losses', label: 'Losses', short: 'L', value: number(record?.losses) },
    { key: 'ties', label: 'Ties', short: 'T', value: number(record?.ties) },
    { key: 'no_results', label: 'No result', short: 'NR', value: number(record?.no_results) },
  ];
  const total = counts.reduce((sum, item) => sum + item.value, 0);
  const segments = counts.map((item) => {
    const width = total ? (item.value / total) * 100 : 0;
    return `<span class="result-segment segment-${item.key}" style="width:${width.toFixed(4)}%" aria-hidden="true"></span>`;
  }).join('');
  const numbers = counts.map((item) => `<div class="outcome-count"><span>${item.label}</span><strong>${formatCount(item.value)}</strong></div>`).join('');
  return `<div class="results-strip${large ? ' is-large' : ''}" role="img" aria-label="${html(counts.map((item) => `${item.label}: ${formatCount(item.value)}`).join(', '))}">${segments}</div>${large ? `<div class="outcome-counts">${numbers}</div>` : ''}`;
}

function recordsView(records) {
  if (!records.length) return '<p class="empty-note">No team records are available for this selection.</p>';
  if (state.team !== 'All') {
    const record = records[0];
    return `<div class="team-record-summary"><div class="record-summary-head"><span class="team-mark" style="--team-colour:${teamColour(record.team)}" aria-hidden="true"></span><h3>${html(record.team)}</h3></div><p class="record-played">${formatCount(record.played)} matches played</p>${resultsStrip(record, true)}</div>`;
  }
  const sorted = records.slice().sort((a, b) => number(b.wins) - number(a.wins) || String(a.team).localeCompare(String(b.team)));
  const rows = sorted.map((record) => `<tr><th scope="row"><span class="team-mark" style="--team-colour:${teamColour(record.team)}" aria-hidden="true"></span><span>${html(record.team)}</span><div class="table-strip" aria-hidden="true">${resultsStrip(record)}</div></th><td>${formatCount(record.played)}</td><td>${formatCount(record.wins)}</td><td>${formatCount(record.losses)}</td><td>${formatCount(record.ties)}</td><td>${formatCount(record.no_results)}</td></tr>`).join('');
  return `<div class="table-scroll results-table-scroll"><table class="results-table"><caption>Teams ranked by wins</caption><thead><tr><th scope="col">Team</th><th scope="col">Played</th><th scope="col">W</th><th scope="col">L</th><th scope="col">T</th><th scope="col">No result</th></tr></thead><tbody>${rows}</tbody></table></div>`;
}

function rankList(items, kind) {
  if (!items.length) return `<p class="empty-note">${html(emptyMessage(kind === 'batters' ? 'batters' : 'bowlers', state.season, state.data))}</p>`;
  const batters = kind === 'batters';
  const metricKey = batters ? 'boundary_percentage' : 'economy';
  const values = items.map((item) => number(item[metricKey]));
  const max = Math.max(...values, 0.0001);
  const rows = items.slice(0, 10).map((item, index) => {
    const value = number(item[metricKey]);
    const width = Math.max(0, Math.min(100, (value / max) * 100));
    const name = batters ? item.batter : item.bowler;
    const secondary = batters
      ? `${formatCount(item.balls_faced)} balls faced, ${formatCount(item.batter_runs)} runs`
      : `${formatCount(item.legal_balls)} legal balls, ${formatCount(item.runs_conceded)} runs`;
    const formatted = batters ? formatPercent(value) : formatNumber(value);
    return `<li class="rank-row"><span class="rank-number" aria-hidden="true">${String(index + 1).padStart(2, '0')}</span><div class="rank-main"><div class="rank-topline"><span class="player-name">${html(name)}</span><strong class="rank-value">${formatted}</strong></div><div class="rank-track" role="img" aria-label="${html(`${name}: ${formatted}`)}"><span class="rank-fill" style="--bar-width:${width.toFixed(3)}%"></span></div><p class="rank-secondary">${secondary}</p></div></li>`;
  }).join('');
  return `<ol class="rank-list">${rows}</ol>`;
}

function deathTable(items) {
  if (!items.length) return `<p class="empty-note">${html(emptyMessage('death_bowlers', state.season, state.data))}</p>`;
  const max = Math.max(...items.map((item) => number(item.economy)), 0.0001);
  const rows = items.slice(0, 10).map((item) => {
    const width = Math.max(0, Math.min(100, (number(item.economy) / max) * 100));
    return `<tr><th scope="row">${html(item.bowler)}<span class="death-mini-bar" aria-hidden="true"><span style="--bar-width:${width.toFixed(3)}%"></span></span></th><td>${formatNumber(item.economy)}</td><td>${formatCount(item.legal_balls)}</td><td>${formatCount(item.runs_conceded)}</td></tr>`;
  }).join('');
  return `<div class="table-scroll death-table-scroll"><table class="death-table"><caption>Overs 16 to 20, ranked by economy</caption><thead><tr><th scope="col">Bowler</th><th scope="col">Economy</th><th scope="col">Balls</th><th scope="col">Runs</th></tr></thead><tbody>${rows}</tbody></table></div>`;
}

function definitionsView() {
  const labels = {
    run_rate: 'Run rate', economy: 'Economy', boundary_percentage: 'Boundary percentage',
    death_over_economy: 'Death-over economy', team_records: 'Team results', qualification_rule: 'Qualification',
  };
  const entries = Object.entries(state.data.definitions || {});
  const definitions = entries.map(([key, value]) => `<div class="definition-item"><dt>${html(labels[key] || key.replaceAll('_', ' '))}</dt><dd>${html(value)}</dd></div>`).join('');
  const thresholds = [
    ['All seasons', state.data.thresholds?.all_seasons],
    ['One season', state.data.thresholds?.single_season],
  ].map(([label, value]) => `<div class="definition-item"><dt>${html(label)}</dt><dd>${formatCount(value)} qualifying balls</dd></div>`).join('');
  return `<dl class="definition-list">${definitions}</dl><dl class="threshold-list"><div class="definition-item"><dt>Sample thresholds</dt><dd>Minimum player sample sizes</dd></div>${thresholds}</dl>`;
}

function updateAccent() {
  const accent = state.team === 'All' ? '#B3202C' : teamColour(state.team);
  document.documentElement.style.setProperty('--accent', accent);
  document.documentElement.style.setProperty('--selected-team', state.team === 'All' ? '#B3202C' : teamColour(state.team));
}

function render({ focusSeason = false } = {}) {
  const data = state.data;
  state.team = normalizeTeamForSeason(data, state.season, state.team);
  updateAccent();
  $('#data-date').textContent = fmtDate(data.data_through);
  $('#match-count').textContent = formatCount(data.match_count);
  $('#active-scope').textContent = `${state.season === 'All' ? 'All seasons' : state.season} / ${state.team === 'All' ? 'All teams' : state.team}`;
  $('#story-headline').textContent = buildHeadline(data, state.season, state.team);
  $('#clear-season').setAttribute('aria-pressed', String(state.season === 'All'));
  $('#run-rate-content').innerHTML = runRateChart();
  $('#team-chips').innerHTML = teamChipMarkup();
  const teams = teamsForSeason(data, state.season);
  $('#team-selection-note').textContent = state.season === 'All'
    ? `${teams.length} franchises in the data`
    : `${teams.length} teams played in ${state.season}`;
  const scope = resolveScope(data, state.season, state.team);
  $('#records-content').innerHTML = recordsView(scope.records);
  $('#bowlers-content').innerHTML = rankList(scope.bowlers, 'bowlers');
  $('#batters-content').innerHTML = rankList(scope.batters, 'batters');
  $('#death-content').innerHTML = deathTable(scope.death_bowlers);
  $('#definitions-content').innerHTML = definitionsView();
  state.renderCount += 1;
  document.body.classList.remove('animate-entry');
  // A single entrance sequence draws the chart, then grows the scorebook bars.
  requestAnimationFrame(() => document.body.classList.add('animate-entry'));
  if (focusSeason && state.season !== 'All') {
    requestAnimationFrame(() => document.querySelector(`.season-point[data-season="${CSS.escape(state.season)}"]`)?.focus());
  }
}

function selectSeason(season, { focus = false } = {}) {
  state.season = season === 'All' ? 'All' : String(season);
  state.team = normalizeTeamForSeason(state.data, state.season, state.team);
  render({ focusSeason: focus });
}

function installEvents() {
  $('#clear-season').addEventListener('click', () => {
    state.season = 'All';
    render();
  });
  $('#team-chips').addEventListener('click', (event) => {
    const button = event.target.closest('button[data-team]');
    if (!button || button.disabled) return;
    state.team = button.dataset.team;
    render();
  });
  $('#run-rate-content').addEventListener('click', (event) => {
    const point = event.target.closest('.season-point[data-season]');
    if (point) selectSeason(point.dataset.season, { focus: true });
  });
  $('#run-rate-content').addEventListener('keydown', (event) => {
    const point = event.target.closest('.season-point[data-season]');
    if (!point) return;
    const seasons = Array.isArray(state.data.seasons) ? state.data.seasons.map(String) : [];
    const current = seasons.indexOf(point.dataset.season);
    if (event.key === 'ArrowRight' || event.key === 'ArrowDown') {
      event.preventDefault();
      selectSeason(seasons[Math.min(seasons.length - 1, current + 1)], { focus: true });
    } else if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') {
      event.preventDefault();
      selectSeason(seasons[Math.max(0, current - 1)], { focus: true });
    } else if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      selectSeason(point.dataset.season, { focus: true });
    } else if (event.key === 'Home' || event.key === 'End') {
      event.preventDefault();
      selectSeason(event.key === 'Home' ? seasons[0] : seasons[seasons.length - 1], { focus: true });
    }
  });
}

async function start() {
  try {
    const response = await fetch('./data/ipl_metrics.json');
    if (!response.ok) throw new Error(`Request failed with ${response.status}`);
    state.data = await response.json();
    state.season = 'All';
    state.team = 'All';
    installEvents();
    render();
    $('#loading-state').hidden = true;
    $('#dashboard').hidden = false;
  } catch (error) {
    console.error('Could not load dashboard JSON:', error);
    $('#loading-state').hidden = true;
    $('#error-state').hidden = false;
  }
}

start();
