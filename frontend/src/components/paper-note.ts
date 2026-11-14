const outlines = [
  "M4 5 Q83 2 157 4 Q206 5 243 3 Q246 58 244 113 Q243 171 245 219 Q170 222 96 220 Q45 219 3 222 Q5 151 3 92 Q2 48 4 5Z",
  "M3 4 Q65 6 127 3 Q187 2 244 5 Q242 63 245 123 Q246 173 243 221 Q165 218 90 221 Q46 223 4 219 Q2 158 4 100 Q5 52 3 4Z",
  "M5 3 Q84 5 164 3 Q202 2 244 4 Q246 68 243 128 Q242 178 245 220 Q166 223 89 220 Q47 218 3 221 Q5 154 3 91 Q2 44 5 3Z",
];

/** The board and its preview share the same subtle paper geometry. */
export function paperOutline(id: string) {
  return outlines[
    Array.from(id).reduce((sum, char) => sum + char.charCodeAt(0), 0) %
      outlines.length
  ];
}
