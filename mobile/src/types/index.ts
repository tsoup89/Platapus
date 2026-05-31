export interface DealScore {
  rating: 'STEAL' | 'GREAT' | 'GOOD' | 'FAIR' | 'PASS';
  score: number;
  estimated_value: number | null;
  conservative_value: number | null;
  target_buy_price: number | null;
  estimated_profit: number | null;
  profit_margin: number | null;
  confidence: number;
  reasons: string[];
  warnings: string[];
}

export interface Listing {
  id: number;
  source: string;
  title: string;
  description: string;
  price: number | null;
  url: string | null;
  image_url: string | null;
  location: string | null;
  seller: string | null;
  first_seen_at: string;
  ignored: boolean;
  alert_sent: boolean;
  deal_score: DealScore | null;
  watchlist_id: number | null;
}

export interface Watchlist {
  id: number;
  name: string;
  enabled: boolean;
  category: string | null;
  keywords: string[];
  locations: string[];
  min_price: number;
  max_price: number;
  min_rating_to_alert: string;
  run_frequency_minutes: number;
}
