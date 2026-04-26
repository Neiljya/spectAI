// src/lib/tracker.ts
// Wrapper for HenrikDev Valorant API
// Docs: https://docs.henrikdev.xyz/

import type { ParsedTrackerData } from '@/types/tracker';

const API_KEY = import.meta.env.VITE_HENRIK_API_KEY as string;
const BASE_URL = 'https://api.henrikdev.xyz/valorant';

const AGENT_ROLES: Record<string, string> = {
  Brimstone: 'Controller', Omen: 'Controller', Viper: 'Controller',
  Astra: 'Controller', Harbor: 'Controller', Clove: 'Controller',
  Jett: 'Duelist', Reyna: 'Duelist', Phoenix: 'Duelist',
  Raze: 'Duelist', Yoru: 'Duelist', Neon: 'Duelist', Iso: 'Duelist',
  Sage: 'Sentinel', Killjoy: 'Sentinel', Cypher: 'Sentinel',
  Chamber: 'Sentinel', Deadlock: 'Sentinel',
  Sova: 'Initiator', Breach: 'Initiator', Skye: 'Initiator',
  'KAY/O': 'Initiator', Fade: 'Initiator', Gekko: 'Initiator',
};

const RANK_TO_TIER: Record<string, number> = {
  Iron: 1, Bronze: 4, Silver: 7, Gold: 10,
  Platinum: 13, Diamond: 16, Ascendant: 19,
  Immortal: 22, Radiant: 25,
};

function rankTier(rankName: string): number {
  const base = Object.keys(RANK_TO_TIER).find(r => rankName?.startsWith(r));
  if (!base) return 0;
  const num = parseInt(rankName.split(' ')[1] ?? '1', 10);
  return RANK_TO_TIER[base] + (num - 1);
}

// ── Helper to bypass local QUIC/UDP blocks ──
async function fetchHenrik(endpoint: string) {
  // We hit our local Vite proxy, which secretly fetches HenrikDev for us
  const targetUrl = `/api/henrik/valorant${endpoint}`;
  
  return fetch(targetUrl, {
    headers: {
      'Authorization': API_KEY,
      'Accept': 'application/json'
    }
  });
}

// ── Fetch & Compute from HenrikDev ─────────────────────────────

export async function fetchTrackerProfile(riotId: string): Promise<ParsedTrackerData | any> {
  const [name, tag] = riotId.split('#');
  
  if (!name || !tag) throw new Error("Invalid Riot ID format. Please use Name#Tag");

  try {
    // 1. Fetch Account (via proxy helper)
    const accountRes = await fetchHenrik(`/v1/account/${encodeURIComponent(name)}/${encodeURIComponent(tag)}`);
    if (!accountRes.ok) throw new Error("Player not found or unauthorized.");
    const accountJson = await accountRes.json();
    const region = accountJson.data.region;

    // 2. Fetch MMR (via proxy helper)
    const mmrRes = await fetchHenrik(`/v2/mmr/${region}/${encodeURIComponent(name)}/${encodeURIComponent(tag)}`);
    const mmrJson = mmrRes.ok ? await mmrRes.json() : null;

    // 3. Fetch Last 10 Matches
    // FIXED: mode=spikerush (No underscore)
    const matchesRes = await fetchHenrik(`/v3/matches/${region}/${encodeURIComponent(name)}/${encodeURIComponent(tag)}?size=10&mode=spikerush`);
    const matchesJson = matchesRes.ok ? await matchesRes.json() : { data: [] };
    const matches = matchesJson.data || [];

    // ── Crunches the Match Data ──
    let totalKills = 0, totalDeaths = 0, totalAssists = 0;
    let totalScore = 0, totalDamage = 0, totalRounds = 0;
    let totalHeadshots = 0, totalShots = 0;
    let matchWins = 0;
    
    const agentMap: Record<string, { matches: number, wins: number, kills: number, deaths: number }> = {};

    matches.forEach((match: any) => {
      // FIXED: Guard against corrupted matches that return without player data
      if (!match?.players?.all_players) return;

      const player = match.players.all_players.find((p: any) => 
        p.name.toLowerCase() === name.toLowerCase() && p.tag.toLowerCase() === tag.toLowerCase()
      );
      if (!player) return;

      const rounds = match.metadata.rounds_played;
      totalRounds += rounds;
      totalKills += player.stats.kills;
      totalDeaths += player.stats.deaths;
      totalAssists += player.stats.assists;
      totalScore += player.stats.score;
      totalDamage += player.damage_made;

      totalHeadshots += player.stats.headshots;
      totalShots += (player.stats.headshots + player.stats.bodyshots + player.stats.legshots);

      const team = player.team.toLowerCase(); 
      const won = match.teams[team]?.has_won;
      if (won) matchWins += 1;

      const agent = player.character;
      if (!agentMap[agent]) agentMap[agent] = { matches: 0, wins: 0, kills: 0, deaths: 0 };
      agentMap[agent].matches += 1;
      agentMap[agent].kills += player.stats.kills;
      agentMap[agent].deaths += player.stats.deaths;
      if (won) agentMap[agent].wins += 1;
    });

    // Calculate Averages
    const gamesPlayed = matches.length || 1; 
    const kd_ratio = totalDeaths > 0 ? totalKills / totalDeaths : totalKills;
    const headshot_pct = totalShots > 0 ? (totalHeadshots / totalShots) * 100 : 0;
    const avg_score = totalRounds > 0 ? totalScore / totalRounds : 0; 
    const avg_damage = totalRounds > 0 ? totalDamage / totalRounds : 0; 
    const win_rate = (matchWins / gamesPlayed) * 100;

    // Process Top Agents
    const agent_prefs = Object.entries(agentMap)
      .map(([agentName, stats]) => ({
        name: agentName,
        role: AGENT_ROLES[agentName] || 'Flex',
        win_rate: (stats.wins / stats.matches) * 100,
        kd: stats.deaths > 0 ? stats.kills / stats.deaths : stats.kills,
        hours: Math.round((stats.matches * 40) / 60), 
        rawMatches: stats.matches
      }))
      .sort((a, b) => b.rawMatches - a.rawMatches) 
      .slice(0, 3); 

    // Generate AI Radar Scores 
    const aim_score = Math.min(Math.max((headshot_pct * 2) + (kd_ratio * 10), 0), 100);
    const util_score = Math.min(Math.max((totalAssists / gamesPlayed) * 10 + 30, 0), 100);
    const mechanics_score = Math.min(Math.max((avg_score / 3), 0), 100);
    const gamesense_score = Math.min(Math.max(win_rate + (kd_ratio * 15), 0), 100);
    const igl_score = 50; 

    const currentRank = mmrJson?.data?.current_data?.currenttierpatched ?? 'Unranked';
    
    // COMPUTE LIFETIME STATS
    let lifetimeWins = 0;
    let lifetimeGames = 0;
    if (mmrJson?.data?.by_season) {
      for (const seasonKey in mmrJson.data.by_season) {
        const season = mmrJson.data.by_season[seasonKey];
        if (!season.error && season.number_of_games) {
          lifetimeWins += season.wins || 0;
          lifetimeGames += season.number_of_games || 0;
        }
      }
    }
    const lifetimeWinRate = lifetimeGames > 0 ? (lifetimeWins / lifetimeGames) * 100 : 0;

    return {
      riot_id: riotId,
      avatar_url: accountJson.data?.card?.small ?? '',
      current_rank: currentRank,
      rank_tier: rankTier(currentRank),
      peak_rank: mmrJson?.data?.highest_rank?.patched_tier ?? currentRank,
      rr: mmrJson?.data?.current_data?.ranking_in_tier ?? 0,
      
      account_level: accountJson.data?.account_level ?? 0,
      elo: mmrJson?.data?.current_data?.elo ?? 0,
      last_mmr_change: mmrJson?.data?.current_data?.mmr_change_to_last_game ?? 0,
      rank_image_url: mmrJson?.data?.current_data?.images?.large ?? '',
      
      lifetime_wins: lifetimeWins,
      lifetime_games: lifetimeGames,
      win_rate: lifetimeWinRate, // Lifetime win rate
      recent_win_rate: win_rate, // Recent 10 games win rate

      kd_ratio: kd_ratio,
      headshot_pct: headshot_pct,
      avg_score: avg_score,
      avg_damage: avg_damage,
      avg_kills: totalKills / gamesPlayed,
      avg_deaths: totalDeaths / gamesPlayed,
      avg_assists: totalAssists / gamesPlayed,
      
      aim_score: Math.round(aim_score),
      util_score: Math.round(util_score),
      mechanics_score: Math.round(mechanics_score),
      gamesense_score: Math.round(gamesense_score),
      igl_score: Math.round(igl_score),
      
      agent_prefs: agent_prefs,
      raw: { account: accountJson.data, mmr: mmrJson?.data, matches: matches },
    };
  } catch (error) {
    console.error("HenrikDev Sync Error:", error);
    throw error;
  }
}