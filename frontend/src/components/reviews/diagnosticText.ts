// Exception messages can contain a raw HTTP request. Keep credentials out of diagnostic surfaces.
export function diagnosticText(message: string) {
  const containsCredential = /\b(?:authorization|proxy-authorization|set-cookie|cookie|x-api-key)["']?\s*:|\bbearer\s+[\w./+=-]+|\b(?:api[_-]?key|access[_-]?token|password|client[_-]?secret)["']?\s*[:=]\s*\S+|\b(?:gh[pousr]_|github_pat_|gsk_)[\w-]+/i.test(message);
  return containsCredential ? 'Diagnostic text withheld because it contains credential information.' : message;
}

export function scannerMessage(scanner: string, message: string) {
  return ['bandit', 'semgrep'].includes(scanner.trim().toLowerCase()) ? diagnosticText(message) : null;
}

export function diagnosticError(error: unknown) {
  return error instanceof Error ? new Error(diagnosticText(error.message)) : error;
}
