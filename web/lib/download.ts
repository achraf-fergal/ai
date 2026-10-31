export async function saveResult(url: string): Promise<void> {
  try {
    const response = await fetch(url);
    if (!response.ok) throw new Error(`audio download failed (${response.status})`);
    const blob = await response.blob();
    const mime = blob.type.toLowerCase();
    const extension = mime.includes("wav") ? "wav" : mime.includes("ogg") ? "ogg" : mime.includes("mp4") ? "m4a" : mime.includes("webm") ? "webm" : "mp3";
    const objectUrl = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = objectUrl;
    anchor.download = `audio-${Date.now()}.${extension}`;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(objectUrl);
  } catch {
    window.open(url, "_blank", "noreferrer");
  }
}
