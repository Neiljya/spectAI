// src/hooks/usePlayer.ts
import { useState, useEffect, useCallback } from 'react';
import { supabase } from '@/lib/supabase';
import { fetchTrackerProfile } from '@/lib/tracker';
import { tagPlaystyle } from '@/lib/playstyleTagger';
import type { Profile, PlayerStats } from '@/types/player';

export function usePlayer(userId: string | undefined) {
  const [profile, setProfile]   = useState<Profile | null>(null);
  const [stats,   setStats]     = useState<PlayerStats | null>(null);
  const [loading, setLoading]   = useState(false);
  const [error,   setError]     = useState<string | null>(null);
  const [syncing, setSyncing]   = useState(false);

  // ── Load profile + latest stats ──────────────────────────
  const load = useCallback(async () => {
    if (!userId) return;
    setLoading(true);
    setError(null);

    try {
      const [profRes, statsRes] = await Promise.all([
        supabase.from('profiles').select('*').eq('id', userId).single(),
        supabase
          .from('player_stats')
          .select('*')
          .eq('profile_id', userId)
          .order('synced_at', { ascending: false })
          .limit(1)
          .maybeSingle(),
      ]);

      if (profRes.error) throw profRes.error;
      setProfile(profRes.data as Profile);
      setStats(statsRes.data as PlayerStats | null);
    } catch (e: unknown) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [userId]);

  useEffect(() => { load(); }, [load]);

  // ── Sync from tracker.gg ─────────────────────────────────
  const syncTracker = useCallback(async (riotId: string) => {
    if (!userId) return;
    setSyncing(true);
    setError(null);

    try {
      // 1. Fetch raw data
      const trackerData = await fetchTrackerProfile(riotId);

      // 2. AI-tag playstyle
      const playstyle = tagPlaystyle(trackerData);

      // 3. Update profile riot_id + avatar
      await supabase.from('profiles').update({
        riot_id:    trackerData.riot_id,
        avatar_url: trackerData.avatar_url,
      }).eq('id', userId);

      // 4. Insert new stats snapshot via RPC
      await supabase.rpc('sync_player_stats', {
        p_profile_id: userId,
        p_stats: {
          ...trackerData,
          playstyle_tags: playstyle.tags,
          playstyle_desc: playstyle.desc,
          aim_score:        playstyle.aim_score,
          gamesense_score:  playstyle.gamesense_score,
          mechanics_score:  playstyle.mechanics_score,
          util_score:       playstyle.util_score,
          igl_score:        playstyle.igl_score,
          raw_tracker_data: trackerData.raw,
        },
      });

      // 5. Reload
      await load();
    } catch (e: unknown) {
      setError((e as Error).message);
    } finally {
      setSyncing(false);
    }
  }, [userId, load]);

  return { profile, stats, loading, syncing, error, reload: load, syncTracker };
}
