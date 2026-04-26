// src/hooks/useAuth.ts
import { useEffect, useState } from 'react';
import type { User } from '@supabase/supabase-js';
import { supabase } from '../lib/supabase';

export function useAuth() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      setUser(data.session?.user ?? null);
      setLoading(false);
    });

    const { data: listener } = supabase.auth.onAuthStateChange((_e, session) => {
      setUser(session?.user ?? null);
    });

    return () => listener.subscription.unsubscribe();
  }, []);

  return {
    user,
    loading,
    signIn:  (email: string, password: string) =>
      supabase.auth.signInWithPassword({ email, password }),
    signUp:  (email: string, password: string, username: string) =>
      supabase.auth.signUp({ email, password, options: { data: { username } } }),
    signOut: () => supabase.auth.signOut(),
  };
}