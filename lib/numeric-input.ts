/**
 * Keep a controlled input limited to an unsigned number while still allowing
 * an in-progress decimal value such as `12.`. This is stricter than
 * `type="number"`, which browsers allow to contain exponent characters.
 */
export function sanitizeUnsignedNumberInput(value: string, allowDecimal = true): string {
  const numericCharacters = value.replace(allowDecimal ? /[^\d.]/g : /\D/g, "");

  if (!allowDecimal) return numericCharacters;

  const decimalIndex = numericCharacters.indexOf(".");
  if (decimalIndex === -1) return numericCharacters;

  return (
    numericCharacters.slice(0, decimalIndex + 1) +
    numericCharacters.slice(decimalIndex + 1).replace(/\./g, "")
  );
}
