import { api } from "@/lib/api";
import type { VerseGroupLike } from "@/components/query/verse-group";

/** Client-side mirror of index/assemble.py's assemble(): resolve a verse or a
 * story group_id to its full parent group (every Dhp verse the story
 * explains, plus every story that explains them), using the plain /verses
 * and /stories lookups since the API does not expose assemble() directly. */

export async function assembleByVerse(verseNumber: number): Promise<VerseGroupLike> {
  const verse = await api.verse(verseNumber);
  if (!verse.story_group_ids.length) {
    throw new Error(
      `Dhp ${verseNumber} has no story_group_ids; it cannot be resolved to a verse-group.`,
    );
  }
  const stories = await Promise.all(verse.story_group_ids.map((gid) => api.story(gid)));
  const verseNumbers = Array.from(new Set(stories.flatMap((s) => s.dhp_verses))).sort(
    (a, b) => a - b,
  );
  const verses = await Promise.all(verseNumbers.map((n) => api.verse(n)));
  return { verse_numbers: verseNumbers, verses, stories };
}

export async function assembleByStory(groupId: string): Promise<VerseGroupLike> {
  const story = await api.story(groupId);
  const verseNumbers = [...story.dhp_verses].sort((a, b) => a - b);
  const verses = await Promise.all(verseNumbers.map((n) => api.verse(n)));
  return { verse_numbers: verseNumbers, verses, stories: [story] };
}
