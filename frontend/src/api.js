let token = '';
export function setToken(value) { token = value; }
export async function api(path, method = 'GET', data) {
  const response = await fetch('/api' + path, {
    method, headers: method === 'GET' ? {} : {'Content-Type': 'application/json', 'X-Studio-Token': token},
    body: data === undefined ? undefined : JSON.stringify(data),
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || 'The studio could not complete that action.');
  return result;
}
export const defaults = {topic: 'What is opening up for me?', deck: 'esoteric-minimal', spread: 'three', duration: 45, voice: 'windows', writer: 'local'};
export const defaultSettings = config => ({...defaults,voice:config.default_voice||'silent'});
export const clock = seconds => `${Math.floor(seconds / 60).toString().padStart(2, '0')}:${Math.floor(seconds % 60).toString().padStart(2, '0')}`;
