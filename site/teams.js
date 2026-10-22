export const NEUTRAL_TEAM_COLOUR = '#5B6578';

// Primary franchise colours, darkened where needed for marks on chalk.
export const TEAM_COLOURS = Object.freeze({
  'Chennai Super Kings': '#806A00',
  'Deccan Chargers': '#59358A',
  'Delhi Capitals': '#0066A5',
  'Gujarat Lions': '#B34816',
  'Gujarat Titans': '#15385B',
  'Kochi Tuskers Kerala': '#41724B',
  'Kolkata Knight Riders': '#693C83',
  'Lucknow Super Giants': '#006D67',
  'Mumbai Indians': '#0057A3',
  'Pune Warriors': '#315D91',
  'Punjab Kings': '#A92839',
  'Rajasthan Royals': '#A32568',
  'Rising Pune Supergiant': '#7B3B51',
  'Royal Challengers Bengaluru': '#9E1F2D',
  'Sunrisers Hyderabad': '#A84A11',
});

export function teamColour(team) {
  return TEAM_COLOURS[String(team ?? '')] || NEUTRAL_TEAM_COLOUR;
}
