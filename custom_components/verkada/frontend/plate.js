export function plateText(attributes = {}) {
  if (!attributes.plate_tracking) return "";
  if (!attributes.last_plate) return "No plate detections yet";
  const seen = attributes.plate_last_seen ? ` · Last seen ${new Date(attributes.plate_last_seen * 1000).toLocaleString()}` : "";
  return `Last plate: ${attributes.last_plate}${seen}`;
}
