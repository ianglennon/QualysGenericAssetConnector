export const TYPE_BADGE: Record<string, string> = {
  string:  'bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-300',
  number:  'bg-green-100 text-green-700 dark:bg-green-950 dark:text-green-300',
  boolean: 'bg-purple-100 text-purple-700 dark:bg-purple-950 dark:text-purple-300',
  array:   'bg-orange-100 text-orange-700 dark:bg-orange-950 dark:text-orange-300',
  object:  'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-300',
}

export function typeBadgeClass(type: string): string {
  return TYPE_BADGE[type] ?? 'bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400'
}
