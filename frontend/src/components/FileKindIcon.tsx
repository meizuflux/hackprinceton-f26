import {
  AudioLines,
  Braces,
  CalendarDays,
  File,
  FileArchive,
  FileSpreadsheet,
  FileText,
  Film,
  Image,
  Mail,
} from "lucide-react";

const IMAGE = new Set([
  "jpeg",
  "jpg",
  "png",
  "gif",
  "webp",
  "bmp",
  "tif",
  "tiff",
  "heic",
]);
const VIDEO = new Set(["mp4", "mov", "3gp", "avi", "mkv", "matroska"]);
const AUDIO = new Set(["wav", "mp3", "m4a", "flac", "ogg", "amr"]);

/** One drawn icon per evidence format family; decorative, the name and type are always shown in text. */
export function FileKindIcon({
  kind,
  format,
  size = 16,
}: {
  kind?: string;
  format: string;
  size?: number;
}) {
  const f = format.toLowerCase();
  const props = { size, "aria-hidden": true, className: "file-kind-icon" };
  if (kind === "image" || IMAGE.has(f)) return <Image {...props} />;
  if (kind === "video" || VIDEO.has(f)) return <Film {...props} />;
  if (kind === "audio" || AUDIO.has(f)) return <AudioLines {...props} />;
  if (f === "eml" || f === "mbox") return <Mail {...props} />;
  if (f === "ics") return <CalendarDays {...props} />;
  if (kind === "table" || f === "csv" || f === "tsv")
    return <FileSpreadsheet {...props} />;
  if (kind === "json" || f === "json" || f === "jsonl")
    return <Braces {...props} />;
  if (f === "zip" || f === "xlsx" || f === "sqlite")
    return <FileArchive {...props} />;
  if (kind === "binary") return <File {...props} />;
  return <FileText {...props} />;
}
