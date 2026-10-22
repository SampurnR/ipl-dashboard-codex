import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

import {
  buildHeadline,
  contrastRatio,
  emptyMessage,
  formatCount,
  formatNumber,
  formatPercent,
  normalizeTeamForSeason,
  resolveScope,
  runRateSeasonChoices,
  teamsForSeason,
  teamChipsForSeason,
  thresholdFor,
} from '../site/lib.js';
import {
  NEUTRAL_TEAM_COLOUR,
  TEAM_COLOURS,
  teamColour,
} from '../site/teams.js';

const fixture = {
  seasons: [2016, 2017],
  teams: ['Delhi Capitals', 'Sunrisers Hyderabad'],
  teams_by_season: {
    2016: ['Sunrisers Hyderabad'],
    2017: ['Delhi Capitals', 'Sunrisers Hyderabad'],
  },
  thresholds: { all_seasons: 60, single_season: 30 },
  run_rate_by_season: {
    All: [
      { season_year: 2009, run_rate: 7.48 },
      { season_year: 2016, run_rate: 8.2 },
      { season_year: 2026, run_rate: 9.88 },
    ],
    'Sunrisers Hyderabad': [
      { season_year: 2013, run_rate: 7.5 },
      { season_year: 2016, run_rate: 8.2 },
      { season_year: 2026, run_rate: 9.3 },
    ],
  },
  scopes: {
    All: {
      All: {
        bowlers: [{ bowler: 'All Scope Bowler' }],
        batters: [],
        death_bowlers: [],
        records: [],
      },
    },
    2016: {
      All: {
        bowlers: [{ bowler: 'Season Bowler' }],
        batters: [{ batter: 'Season Batter' }],
        death_bowlers: [],
        records: [{ team: 'Sunrisers Hyderabad', wins: 1 }],
      },
      'Sunrisers Hyderabad': {
        bowlers: [{ bowler: 'Rashid Khan' }],
        batters: [{ batter: 'David Warner' }],
        death_bowlers: [{ bowler: 'Bhuvneshwar Kumar' }],
        records: [{ team: 'Sunrisers Hyderabad', wins: 1 }],
      },
    },
  },
};

test('teamsForSeason returns all teams and only teams in a selected season', () => {
  assert.deepEqual(teamsForSeason(fixture, 'All'), fixture.teams);
  assert.deepEqual(teamsForSeason(fixture, 2016), ['Sunrisers Hyderabad']);
});

test('normalizeTeamForSeason resets a team that did not play in the chosen season', () => {
  assert.equal(normalizeTeamForSeason(fixture, 2016, 'Delhi Capitals'), 'All');
  assert.equal(normalizeTeamForSeason(fixture, 2017, 'Delhi Capitals'), 'Delhi Capitals');
});

test('resolveScope handles All/All and a normal season/team scope', () => {
  assert.deepEqual(resolveScope(fixture, 'All', 'All'), {
    bowlers: [{ bowler: 'All Scope Bowler' }], batters: [], death_bowlers: [], records: [],
  });
  assert.deepEqual(resolveScope(fixture, 2016, 'Sunrisers Hyderabad'), {
    bowlers: [{ bowler: 'Rashid Khan' }],
    batters: [{ batter: 'David Warner' }],
    death_bowlers: [{ bowler: 'Bhuvneshwar Kumar' }],
    records: [{ team: 'Sunrisers Hyderabad', wins: 1 }],
  });
});

test('resolveScope returns four empty lists for a missing team or season', () => {
  const empty = { bowlers: [], batters: [], death_bowlers: [], records: [] };
  assert.deepEqual(resolveScope(fixture, 2016, 'Delhi Capitals'), empty);
  assert.deepEqual(resolveScope(fixture, 2015, 'All'), empty);
});

test('thresholdFor uses the all-season and selected-season thresholds', () => {
  assert.equal(thresholdFor(fixture, 'All'), 60);
  assert.equal(thresholdFor(fixture, 2016), 30);
});

test('emptyMessage explains the applicable sample threshold', () => {
  assert.match(emptyMessage('bowlers', 'All', fixture), /60 legal balls/);
  assert.match(emptyMessage('batters', 2016, fixture), /30 balls faced/);
});

test('number formatters keep two decimals for rates and percentages', () => {
  assert.equal(formatNumber(6.6), '6.60');
  assert.equal(formatPercent(80), '80.00%');
  assert.equal(formatPercent(87.55), '87.55%');
  assert.equal(formatCount(1105), '1,105');
  assert.equal(formatNumber('invalid'), '—');
});

test('buildHeadline tells the league-wide, season, and team scoring stories', () => {
  assert.equal(
    buildHeadline(fixture, 'All', 'All'),
    'Scoring has risen from 7.48 runs an over in 2009 to 9.88 in 2026.',
  );
  assert.equal(
    buildHeadline(fixture, 2016, 'All'),
    'The league scored at 8.20 runs an over in 2016.',
  );
  assert.equal(
    buildHeadline(fixture, 'All', 'Sunrisers Hyderabad'),
    'Sunrisers Hyderabad moved from 7.50 runs an over in 2013 to 9.30 in 2026.',
  );
});

test('buildHeadline falls back to a plain title when run-rate data is missing', () => {
  assert.equal(buildHeadline({ run_rate_by_season: {} }, 'All', 'All'), 'IPL scoring by season');
});

test('teamColour returns a mapped color and a neutral fallback', () => {
  assert.match(teamColour('Sunrisers Hyderabad'), /^#[\da-f]{6}$/i);
  assert.equal(teamColour('Unknown XI'), NEUTRAL_TEAM_COLOUR);
});

test('contrastRatio follows WCAG relative luminance', () => {
  assert.equal(contrastRatio('#000000', '#FFFFFF'), 21);
  assert.ok(contrastRatio('#101B33', '#F5F6F4') > 15);
});

test('every dashboard team has a valid color and mapped colors contrast with chalk', () => {
  const data = JSON.parse(readFileSync(new URL('../site/data/ipl_metrics.json', import.meta.url), 'utf8'));
  assert.equal(teamColour('Chennai Super Kings'), '#B28800');
  assert.ok(contrastRatio(teamColour('Chennai Super Kings'), '#F5F6F4') >= 3);
  assert.equal(teamColour('Deccan Chargers'), '#005A9C');
  assert.ok(contrastRatio(teamColour('Deccan Chargers'), '#F5F6F4') >= 3);
  for (const team of data.teams) {
    assert.match(teamColour(team), /^#[\da-f]{6}$/i, `${team} has a valid color`);
  }
  for (const [team, colour] of Object.entries(TEAM_COLOURS)) {
    assert.ok(contrastRatio(colour, '#F5F6F4') >= 3, `${team} contrast is at least 3:1`);
  }
});

test('team chips use season participation to disable non-playing teams', () => {
  assert.deepEqual(teamChipsForSeason(fixture, 'All'), [
    { team: 'Delhi Capitals', disabled: false },
    { team: 'Sunrisers Hyderabad', disabled: false },
  ]);
  assert.deepEqual(teamChipsForSeason(fixture, 2016), [
    { team: 'Delhi Capitals', disabled: true },
    { team: 'Sunrisers Hyderabad', disabled: false },
  ]);
});

test('run-rate season choices keep every season reachable when a team did not play', () => {
  const choices = runRateSeasonChoices({
    seasons: [2016, 2017],
    run_rate_by_season: {
      All: [
        { season_year: 2016, run_rate: 8.4 },
        { season_year: 2017, run_rate: 8.6 },
      ],
      'Sunrisers Hyderabad': [{ season_year: 2016, run_rate: 8.8 }],
    },
  }, 'Sunrisers Hyderabad');
  assert.deepEqual(choices, [
    { season: '2016', row: { season_year: 2016, run_rate: 8.8 }, teamPlayed: true },
    { season: '2017', row: { season_year: 2017, run_rate: 8.6 }, teamPlayed: false },
  ]);
});
