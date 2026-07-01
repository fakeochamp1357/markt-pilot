/**
 * UUID-v4-Generator mit Fallback für ältere Browser / Test-Umgebungen.
 *
 * Primärquelle: ``crypto.randomUUID()`` (alle Evergreen-Browser seit 2022,
 * Node 19+, auch in Service-Worker-Kontexten). Fallback ist eine simple
 * pseudo-random Implementierung, die NICHT kryptografisch stark ist —
 * für Client-Op-Ids reicht das aber (Kollisionsrisiko bei <2^122 vernachlässigbar).
 */
export function newUuid(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  // Fallback: 16 random bytes in UUID-v4-Form gießen
  const bytes = new Uint8Array(16);
  if (typeof crypto !== 'undefined' && crypto.getRandomValues) {
    crypto.getRandomValues(bytes);
  } else {
    for (let i = 0; i < 16; i++) bytes[i] = Math.floor(Math.random() * 256);
  }
  // Version 4 (random) und Variant 10xx setzen
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, "0"));
  return (
    hex.slice(0, 4).join("") +
    "-" +
    hex.slice(4, 6).join("") +
    "-" +
    hex.slice(6, 8).join("") +
    "-" +
    hex.slice(8, 10).join("") +
    "-" +
    hex.slice(10, 16).join("")
  );
}
