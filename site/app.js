import {
  emptyMessage,
  formatCount,
  formatNumber,
  formatPercent,
  normalizeTeamForSeason,
  resolveScope,
  teamsForSeason,
} from './lib.js';

const SVG_NS = 'http://www.w3.org/2000/svg';
const $ = (selector) => document.querySelector(selector);

const loadingState = $('#loading-state');
const errorState = $('#error-state');
const dashboard = $('#dashboard');
const seasonFilter = $('#season-filter');
const teamFilter = $('#team-filter');
const activeScope = $('#active-scope');
let data;

function svgElement(tag, attributes = {}, text = '') {
  const element = document.createElementNS(SVG_NS, tag);
  for (const [key, value] of Object.entries(attributes)) {
    element.setAttribute(key, String(value));
  }
  if (text) element.textContent = text;
  return element;
}

function textElement(tag, className, text) {
  const element = document.createElement(tag);
  element.className = className;
  element.textContent = text;
  return element;
}

function selectedSeason() {
  return seasonFilter.value || 'All';
}

function selectedTeam() {
  return teamFilter.value || 'All';
}

function addOption(select, value, label) {
  const option = document.createElement('option');
  option.value = value;
  option.textContent = label;
  select.append(option);
}

function populateTeams() {
  const currentTeam = normalizeTeamForSeason(data, selectedSeason(), selectedTeam());
  const teams = teamsForSeason(data, selectedSeason());
  teamFilter.replaceChildren();
  addOption(teamFilter, 'All', 'All teams');
  for (const team of teams) addOption(teamFilter, team, team);
  teamFilter.value = currentTeam;
}

function renderRecordSummary(records, team) {
  const container = $('#records-content');
  container.replaceChildren();

  if (team !== 'All') {
    const record = records.find((row) => row.team === team);
    if (!record) {
      container.append(textElement('p', 'record-empty', 'No match records for this selection.'));
      return;
    }
    const values = [
      ['Played', record.played],
      ['Wins', record.wins],
      ['Losses', record.losses],
      ['Ties', record.ties],
      ['No result', record.no_results],
    ];
    const counts = document.createElement('dl');
    counts.className = 'record-counts';
    for (const [label, value] of values) {
      const item = document.createElement('div');
      item.className = 'record-count';
      item.append(textElement('dt', '', label));
      item.append(textElement('dd', '', formatCount(value)));
      counts.append(item);
    }
    container.append(counts);
    return;
  }

  if (!records.length) {
    container.append(textElement('p', 'record-empty', 'No match records for this selection.'));
    return;
  }

  const sorted = [...records].sort((first, second) =>
    Number(second.wins || 0) - Number(first.wins || 0)
    || String(first.team || '').localeCompare(String(second.team || '')));
  const wrap = document.createElement('div');
  wrap.className = 'records-table-wrap';
  const table = document.createElement('table');
  table.className = 'records-table';
  table.innerHTML = '<thead><tr><th scope="col">Team</th><th scope="col">Played</th><th scope="col">W</th><th scope="col">L</th><th scope="col">T</th><th scope="col">No result</th></tr></thead>';
  const body = document.createElement('tbody');
  for (const row of sorted) {
    const tr = document.createElement('tr');
    const values = [row.team, row.played, row.wins, row.losses, row.ties, row.no_results];
    values.forEach((value, index) => {
      const cell = document.createElement('td');
      cell.textContent = index === 0 ? String(value || '') : formatCount(value);
      tr.append(cell);
    });
    body.append(tr);
  }
  table.append(body);
  wrap.append(table);
  container.append(wrap);
}

function renderRunRate(season, team) {
  const container = $('#run-rate-content');
  container.replaceChildren();
  const seriesKey = team === 'All' ? 'All' : team;
  const rows = data.run_rate_by_season?.[seriesKey];
  if (!Array.isArray(rows) || !rows.length) {
    container.append(textElement('p', 'chart-empty', 'No run-rate data for this selection.'));
    return;
  }

  const width = 960;
  const height = 330;
  const left = 82;
  const right = 22;
  const top = 32;
  const bottom = 58;
  const plotWidth = width - left - right;
  const plotHeight = height - top - bottom;
  const values = rows.map((row) => Number(row.run_rate));
  const low = Math.min(...values);
  const high = Math.max(...values);
  const span = high - low || 1;
  const positions = rows.map((row, index) => ({
    row,
    x: rows.length === 1 ? left + plotWidth / 2 : left + (index * plotWidth) / (rows.length - 1),
    y: top + ((high - Number(row.run_rate)) / span) * plotHeight,
  }));

  const chart = svgElement('svg', {
    class: 'run-rate-svg',
    viewBox: `0 0 ${width} ${height}`,
    role: 'img',
    'aria-labelledby': 'run-rate-svg-title run-rate-svg-description',
  });
  chart.append(svgElement('title', { id: 'run-rate-svg-title' }, `Run rate by season for ${seriesKey === 'All' ? 'all teams' : seriesKey}`));
  chart.append(svgElement('desc', { id: 'run-rate-svg-description' }, 'A line chart of the run-rate values supplied for each season. The selected season is emphasized.'));
  chart.append(svgElement('text', { x: left, y: 17, class: 'svg-axis-title' }, 'Run rate (runs per 6 legal balls)'));
  chart.append(svgElement('text', { x: width / 2, y: height - 7, 'text-anchor': 'middle', class: 'svg-axis-title' }, 'Season'));

  for (let row = 0; row < 4; row += 1) {
    const y = top + (row * plotHeight) / 3;
    const tickValue = high - (row * span) / 3;
    chart.append(svgElement('line', { x1: left, y1: y, x2: width - right, y2: y, class: 'svg-gridline' }));
    chart.append(svgElement('text', {
      x: left - 8,
      y: y + 4,
      'text-anchor': 'end',
      class: 'svg-y-tick',
    }, formatNumber(tickValue)));
  }
  chart.append(svgElement('line', { x1: left, y1: top, x2: left, y2: top + plotHeight, class: 'svg-axis' }));
  chart.append(svgElement('line', { x1: left, y1: top + plotHeight, x2: width - right, y2: top + plotHeight, class: 'svg-axis' }));

  const pathData = positions.map((point, index) => `${index === 0 ? 'M' : 'L'} ${point.x} ${point.y}`).join(' ');
  chart.append(svgElement('path', { d: pathData, class: 'svg-run-line' }));
  for (const [index, point] of positions.entries()) {
    const isSelected = season !== 'All' && String(point.row.season_year) === String(season);
    chart.append(svgElement('circle', {
      cx: point.x,
      cy: point.y,
      r: isSelected ? 6 : 4,
      class: isSelected ? 'svg-run-point selected' : 'svg-run-point',
    }));
    chart.append(svgElement('text', {
      x: point.x,
      y: point.y - (index % 2 === 0 ? 12 : 22),
      'text-anchor': 'middle',
      class: isSelected ? 'svg-point-label selected' : 'svg-point-label',
    }, formatNumber(point.row.run_rate)));
    chart.append(svgElement('text', {
      x: point.x,
      y: top + plotHeight + 19,
      'text-anchor': 'middle',
      class: 'svg-season-label',
    }, String(point.row.season_year)));
  }
  const frame = document.createElement('div');
  frame.className = 'chart-frame';
  frame.append(chart);
  container.append(frame);
}

function renderBarChart(containerSelector, rows, kind) {
  const container = $(containerSelector);
  container.replaceChildren();
  if (!Array.isArray(rows) || !rows.length) {
    container.append(textElement('p', 'chart-empty', emptyMessage(kind, selectedSeason(), data)));
    return;
  }

  const isBowler = kind === 'bowlers';
  const valueKey = isBowler ? 'economy' : 'boundary_percentage';
  const labelKey = isBowler ? 'bowler' : 'batter';
  const label = isBowler ? 'Economy (runs per 6 legal balls)' : 'Boundary runs (% of batter runs)';
  const values = rows.map((row) => Number(row[valueKey]));
  const maximum = Math.max(0, ...values);
  const width = 900;
  const top = 38;
  const rowHeight = 36;
  const height = top + rows.length * rowHeight + 12;
  const compact = window.innerWidth <= 1100;
  const trackX = compact ? 230 : 265;
  const trackWidth = compact ? 135 : 340;
  const valueX = compact ? 385 : 635;
  const chart = svgElement('svg', {
    class: 'bar-chart-svg',
    viewBox: `0 0 ${width} ${height}`,
    role: 'img',
    'aria-labelledby': `${kind}-chart-title`,
  });
  chart.append(svgElement('title', { id: `${kind}-chart-title` }, label));
  chart.append(svgElement('text', { x: trackX, y: 20, class: 'svg-axis-title' }, label));
  rows.forEach((row, index) => {
    const y = top + index * rowHeight;
    const value = Number(row[valueKey]);
    const barWidth = maximum > 0 ? (value / maximum) * trackWidth : 0;
    chart.append(svgElement('text', { x: 8, y: y + 16, class: 'svg-bar-name' }, String(row[labelKey] || '')));
    chart.append(svgElement('rect', { x: trackX, y, width: trackWidth, height: 18, rx: 4, class: 'svg-bar-track' }));
    chart.append(svgElement('rect', { x: trackX, y, width: barWidth, height: 18, rx: 4, class: 'svg-bar-fill' }));
    chart.append(svgElement('text', { x: valueX, y: y + 15, class: 'svg-bar-value' }, isBowler ? formatNumber(value) : formatPercent(value)));
  });
  const frame = document.createElement('div');
  frame.className = 'chart-frame';
  frame.append(chart);
  container.append(frame);
}

function renderDeathTable(rows, season) {
  const container = $('#death-content');
  container.replaceChildren();
  if (!Array.isArray(rows) || !rows.length) {
    container.append(textElement('p', 'chart-empty', emptyMessage('death_bowlers', season, data)));
    return;
  }

  const wrap = document.createElement('div');
  wrap.className = 'death-table-wrap';
  const table = document.createElement('table');
  table.className = 'death-table';
  table.innerHTML = '<thead><tr><th scope="col">Bowler</th><th scope="col">Economy</th><th scope="col">Balls</th><th scope="col">Runs</th></tr></thead>';
  const body = document.createElement('tbody');
  for (const row of rows) {
    const tr = document.createElement('tr');
    const values = [row.bowler, formatNumber(row.economy), formatCount(row.legal_balls), formatCount(row.runs_conceded)];
    values.forEach((value, index) => {
      const cell = document.createElement('td');
      cell.textContent = index === 0 ? String(value || '') : value;
      tr.append(cell);
    });
    body.append(tr);
  }
  table.append(body);
  wrap.append(table);
  container.append(wrap);
}

const DEFINITION_LABELS = {
  run_rate: 'Run rate',
  economy: 'Bowler economy',
  boundary_percentage: 'Boundary %',
  death_over_economy: 'Death-over economy',
  team_records: 'W/L/T',
  qualification_rule: 'Qualification rule',
};

function renderDefinitions() {
  const container = $('#definitions-content');
  container.replaceChildren();
  const definitionList = document.createElement('dl');
  definitionList.className = 'definition-list';
  for (const [key, definition] of Object.entries(data.definitions || {})) {
    const label = DEFINITION_LABELS[key] || key.replaceAll('_', ' ');
    definitionList.append(textElement('dt', '', label));
    definitionList.append(textElement('dd', '', definition));
  }
  const thresholdList = document.createElement('dl');
  thresholdList.className = 'threshold-list';
  const thresholds = data.thresholds || {};
  const entries = [
    ['All seasons', thresholds.all_seasons],
    ['One season', thresholds.single_season],
  ];
  for (const [label, value] of entries) {
    thresholdList.append(textElement('dt', '', `${label} threshold`));
    thresholdList.append(textElement('dd', '', `${formatCount(value)} balls`));
  }
  container.append(definitionList, thresholdList);
}

function renderDashboard() {
  const season = selectedSeason();
  const team = selectedTeam();
  activeScope.textContent = `${season === 'All' ? 'All seasons' : season} · ${team === 'All' ? 'All teams' : team}`;
  const scope = resolveScope(data, season, team);
  renderRecordSummary(scope.records, team);
  renderRunRate(season, team);
  renderBarChart('#bowlers-content', scope.bowlers, 'bowlers');
  renderBarChart('#batters-content', scope.batters, 'batters');
  renderDeathTable(scope.death_bowlers, season);
}

function populateSeasons() {
  const seasons = Array.isArray(data.seasons) ? [...data.seasons] : [];
  seasons.sort((first, second) => Number(second) - Number(first));
  seasonFilter.replaceChildren();
  addOption(seasonFilter, 'All', 'All seasons');
  for (const season of seasons) addOption(seasonFilter, String(season), String(season));
}

async function start() {
  try {
    const response = await fetch('./data/ipl_metrics.json');
    if (!response.ok) throw new Error(`Metrics JSON returned HTTP ${response.status}`);
    data = await response.json();
    $('#data-meta').textContent = `Data through ${data.data_through} · ${formatCount(data.match_count)} matches`;
    populateSeasons();
    populateTeams();
    renderDefinitions();
    renderDashboard();
    loadingState.hidden = true;
    dashboard.hidden = false;
  } catch (error) {
    loadingState.hidden = true;
    errorState.hidden = false;
    console.error('Unable to load IPL metrics. Serve the site over HTTP and retry.', error);
  }
}

seasonFilter.addEventListener('change', () => {
  populateTeams();
  renderDashboard();
});

teamFilter.addEventListener('change', renderDashboard);
window.addEventListener('resize', () => {
  if (data) renderDashboard();
});

start();
