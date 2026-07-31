import { get } from "./client";

import type {
  AudioAcousticRead,
  AudioAnalysisRead,
  AudioAssetRead,
  AudioDownloadData,
  AudioMetadataRead,
  AudioSegmentsRead,
  AudioSpeechRead,
  AudioTechnicalRead,
} from "@/types/domain";

export async function getAudioAsset(audioId: string): Promise<AudioAssetRead> {
  return get<AudioAssetRead>(`/audio/${audioId}`);
}

export async function getAudioMetadata(audioId: string): Promise<AudioMetadataRead> {
  return get<AudioMetadataRead>(`/audio/${audioId}/metadata`);
}

export async function getAudioDownload(audioId: string): Promise<AudioDownloadData> {
  return get<AudioDownloadData>(`/audio/${audioId}/download`);
}

export async function getAudioAnalysis(audioId: string): Promise<AudioAnalysisRead> {
  return get<AudioAnalysisRead>(`/audio/${audioId}/analysis`);
}

export async function getAudioSegments(audioId: string): Promise<AudioSegmentsRead> {
  return get<AudioSegmentsRead>(`/audio/${audioId}/segments`);
}

export async function getAudioTechnical(
  audioId: string,
): Promise<AudioTechnicalRead> {
  return get<AudioTechnicalRead>(`/audio/${audioId}/technical`);
}

export async function getAudioAcoustic(audioId: string): Promise<AudioAcousticRead> {
  return get<AudioAcousticRead>(`/audio/${audioId}/acoustic`);
}

export async function getAudioSpeech(audioId: string): Promise<AudioSpeechRead> {
  return get<AudioSpeechRead>(`/audio/${audioId}/speech`);
}

export const audioApi = {
  getAudioAsset,
  getAudioMetadata,
  getAudioDownload,
  getAudioAnalysis,
  getAudioSegments,
  getAudioTechnical,
  getAudioAcoustic,
  getAudioSpeech,
};
