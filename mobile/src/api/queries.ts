import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import client from './client';
import type { Listing, Watchlist } from '../types';

// ── Listings ────────────────────────────────────────────────

export function useListings(params?: { ignored?: boolean; limit?: number }) {
  return useQuery({
    queryKey: ['listings', params],
    queryFn: async () => {
      const res = await client.get<Listing[]>('/listings', {
        params: { ignored: false, limit: 100, ...params },
      });
      return res.data;
    },
    refetchInterval: 60_000,
  });
}

export function useIgnoreListing() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => client.post(`/listings/${id}/ignore`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['listings'] }),
  });
}

export function useFullPipeline() {
  return useMutation({
    // Mobile queues for the desktop to process (phone can't run Playwright).
    mutationFn: (id: number) => client.post(`/listings/${id}/queue-pipeline`),
  });
}

// ── Watchlists ───────────────────────────────────────────────

export function useWatchlists() {
  return useQuery({
    queryKey: ['watchlists'],
    queryFn: async () => {
      const res = await client.get<Watchlist[]>('/watchlists');
      return res.data;
    },
  });
}

export function useToggleWatchlist() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => client.post(`/watchlists/${id}/toggle`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['watchlists'] }),
  });
}
