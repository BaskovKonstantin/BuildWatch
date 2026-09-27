// Shared presentation helpers: ЛТЦ object types, equipment labels, dates.

// Object types from the ЛТЦ work catalog header, each with an iOS system tint.
export const OBJECT_TYPES: { name: string; tint: string }[] = [
  { name: "Жильё", tint: "orange" },
  { name: "Образование", tint: "blue" },
  { name: "Здравоохранение", tint: "red" },
  { name: "Спорт", tint: "green" },
  { name: "Культура", tint: "purple" },
  { name: "Административные здания", tint: "indigo" },
  { name: "ДОУ", tint: "yellow" },
  { name: "Офисно-деловой центр", tint: "teal" },
  { name: "Дороги", tint: "gray" },
];

export function typeTint(type: string): string {
  return OBJECT_TYPES.find((t) => t.name === type)?.tint ?? "blue";
}

export const DISTRICTS = [
  "ЦАО", "САО", "СВАО", "ВАО", "ЮВАО", "ЮАО", "ЮЗАО", "ЗАО", "СЗАО", "ЗелАО", "НАО", "ТАО",
];

const EQUIPMENT_RU: Record<string, string> = {
  excavator: "Экскаватор",
  "dump truck": "Самосвал",
  truck: "Грузовик",
  bulldozer: "Бульдозер",
  loader: "Погрузчик",
  grader: "Грейдер",
  "road roller": "Каток",
  "concrete mixer": "Бетоносмеситель",
  "concrete pump": "Бетононасос",
  "mobile crane": "Автокран",
  "truck crane": "Автокран",
  "tower crane": "Башенный кран",
  "crane manipulator": "Кран-манипулятор",
  "drilling rig": "Буровая установка",
  worker: "Рабочий",
  "safety helmet": "Каска",
  vest: "Жилет",
};

export function equipmentRu(label: string): string {
  return EQUIPMENT_RU[label] ?? label;
}

/** Distinct Russian names: truck crane and mobile crane both read «Автокран». */
export function equipmentList(labels: string[]): string[] {
  return [...new Set(labels.map(equipmentRu))];
}

const MONTHS_SHORT = ["янв.", "февр.", "мар.", "апр.", "мая", "июн.", "июл.", "авг.", "сент.", "окт.", "нояб.", "дек."];
const MONTHS_FULL = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря"];

function parts(iso: string): [number, number, number] {
  const [y, m, d] = iso.slice(0, 10).split("-").map(Number);
  return [y, m, d];
}

/** 22 сент. (year added when it differs from the current one). */
export function shortDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const [y, m, d] = parts(iso);
  const year = y !== new Date().getFullYear() ? ` ${y}` : "";
  return `${d} ${MONTHS_SHORT[m - 1]}${year}`;
}

/** 22 сентября 2026 */
export function longDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const [y, m, d] = parts(iso);
  return `${d} ${MONTHS_FULL[m - 1]} ${y}`;
}

/** 22.09.2026 */
export function numericDate(iso: string): string {
  const [y, m, d] = iso.slice(0, 10).split("-");
  return `${d}.${m}.${y}`;
}

export function todayTitle(): string {
  const s = new Date().toLocaleDateString("ru-RU", { weekday: "long", day: "numeric", month: "long" });
  return s.charAt(0).toUpperCase() + s.slice(1);
}

/** plural(3, ["снимок","снимка","снимков"]) → «снимка» */
export function plural(n: number, forms: [string, string, string]): string {
  const m10 = n % 10, m100 = n % 100;
  if (m10 === 1 && m100 !== 11) return forms[0];
  if (m10 >= 2 && m10 <= 4 && (m100 < 12 || m100 > 14)) return forms[1];
  return forms[2];
}
