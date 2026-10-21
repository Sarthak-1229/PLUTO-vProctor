"""Trie (Prefix Tree) for skill and keyword autocomplete.

Time complexity:
    insert: O(L) where L = length of word
    search: O(L)
    starts_with: O(P) where P = length of prefix
    autocomplete: O(P + N) where N = number of nodes visited

Space complexity: O(SIGMA * L * W) where SIGMA = alphabet size, W = number of words
"""
from __future__ import annotations
from typing import Dict, List, Optional


class TrieNode:
    """Node in a Trie with character children and end-of-word flag."""

    def __init__(self) -> None:
        self.children: Dict[str, "TrieNode"] = {}
        self.is_end: bool = False


class Trie:
    """Prefix tree for fast skill lookup and autocomplete in job/skill search.

    Attributes:
        root: Root TrieNode.
    """

    def __init__(self) -> None:
        self.root = TrieNode()

    def insert(self, word: str) -> None:
        """Insert a word into the Trie.

        Args:
            word: String to insert (case-insensitive, lowercased internally).
        """
        node = self.root
        for ch in word.lower():
            if ch not in node.children:
                node.children[ch] = TrieNode()
            node = node.children[ch]
        node.is_end = True

    def search(self, word: str) -> bool:
        """Check if an exact word exists in the Trie.

        Args:
            word: The word to search for.

        Returns:
            True if the word is present, False otherwise.
        """
        node = self._get_node(word.lower())
        return node is not None and node.is_end

    def starts_with(self, prefix: str) -> bool:
        """Check if any word starts with the given prefix.

        Args:
            prefix: The prefix to check.

        Returns:
            True if at least one word has this prefix.
        """
        return self._get_node(prefix.lower()) is not None

    def autocomplete(self, prefix: str) -> List[str]:
        """Return all words starting with the given prefix.

        Args:
            prefix: Prefix to autocomplete.

        Returns:
            Sorted list of matching words.
        """
        node = self._get_node(prefix.lower())
        if node is None:
            return []
        results: List[str] = []
        self._dfs(node, list(prefix.lower()), results)
        return sorted(results)

    def _get_node(self, prefix: str) -> Optional[TrieNode]:
        """Traverse the Trie to the node at the end of prefix.

        Returns None if prefix is not found.
        """
        node = self.root
        for ch in prefix:
            if ch not in node.children:
                return None
            node = node.children[ch]
        return node

    def _dfs(self, node: TrieNode, current: List[str], results: List[str]) -> None:
        """Depth-first search to collect all complete words from node."""
        if node.is_end:
            results.append("".join(current))
        for ch, child in node.children.items():
            current.append(ch)
            self._dfs(child, current, results)
            current.pop()
