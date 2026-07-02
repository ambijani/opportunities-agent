/** Ed25519 signature verification using the Web Crypto API (required by Discord). */

function hexToBytes(hex: string): Uint8Array {
  const bytes = new Uint8Array(hex.length / 2);
  for (let i = 0; i < hex.length; i += 2) {
    bytes[i / 2] = parseInt(hex.slice(i, i + 2), 16);
  }
  return bytes;
}

export async function verifyDiscordSignature(
  request: Request,
  publicKeyHex: string
): Promise<boolean> {
  const signature = request.headers.get("X-Signature-Ed25519");
  const timestamp = request.headers.get("X-Signature-Timestamp");
  if (!signature || !timestamp) return false;

  const body = await request.clone().text();
  const message = new TextEncoder().encode(timestamp + body);

  try {
    const cryptoKey = await crypto.subtle.importKey(
      "raw",
      hexToBytes(publicKeyHex),
      { name: "Ed25519", namedCurve: "Ed25519" },
      false,
      ["verify"]
    );
    return crypto.subtle.verify("Ed25519", cryptoKey, hexToBytes(signature), message);
  } catch {
    return false;
  }
}
