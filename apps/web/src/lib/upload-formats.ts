export const ACCEPTED_UPLOAD_EXTENSIONS = [
  ".mp4",
  ".mkv",
  ".mov",
  ".avi",
  ".webm",
  ".mp3",
  ".wav",
  ".m4a",
  ".aac",
  ".opus",
  ".srt",
  ".vtt",
  ".txt",
] as const;

export const UPLOAD_ACCEPT = [
  "video/*",
  "audio/*",
  ...ACCEPTED_UPLOAD_EXTENSIONS,
  ...ACCEPTED_UPLOAD_EXTENSIONS.map((ext) => ext.toUpperCase()),
].join(",");
