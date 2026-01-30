export async function loadSharedConstants() {
  try {
    const res = await fetch("/public/shared/constants.json");
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}
