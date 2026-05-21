import { client as apiClient } from './client';

export interface VideoProgressPayload {
  training_id: string;
  chapter_id: string;
  position_seconds: number;
  milestone_25?: boolean;
  milestone_50?: boolean;
  milestone_75?: boolean;
  milestone_100?: boolean;
  video_ended?: boolean;
}

export interface VideoProgressResponse {
  status: string;
  resume_position_seconds: number;
}

export const postVideoProgress = (
  data: VideoProgressPayload,
): Promise<VideoProgressResponse> =>
  apiClient.post<VideoProgressResponse>('/progress/video', data);
