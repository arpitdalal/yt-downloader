// Types for the Electron app (no database needed)

export interface VideoInfo {
  id: string;
  title: string;
  duration: number | null;
  is_live: boolean;
  is_scheduled: boolean;
  scheduled_start_time: string | null;
  thumbnail: string | null;
  uploader: string | null;
}
