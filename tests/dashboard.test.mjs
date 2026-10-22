import test from 'node:test';
import assert from 'node:assert/strict';

import {
  emptyMessage,
  normalizeTeamForSeason,
  resolveScope,
  teamsForSeason,
  thresholdFor,
} from '../site/lib.js';

const fixture = {
  seasons: [2016, 2017],
  teams: ['Delhi Capitals', 'Sunrisers Hyderabad'],
  teams_by_season: {
    2016: ['Sunrisers Hyderabad'],
    2017: ['Delhi Capitals', 'Sunrisers Hyderabad'],
  },
  thresholds: { all_seasons: 60, single_season: 30 },
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
