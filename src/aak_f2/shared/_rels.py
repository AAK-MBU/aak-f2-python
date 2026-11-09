"""Link relation names used by F2-REST."""

CASEFILE_REL_PREFIX = "http://cbrain.com/casefile/rel/"

_STANDARD_RELS = frozenset({"self", "up", "down", "alternate", "next", "previous"})


def full_rel(rel: str) -> str:
    """Return the full link relation name for ``rel``.

    Standard relations (``self``, ``up``, ``down``, ...) and full URIs are returned
    unchanged. Any other name is treated as an F2 relation, so ``"case-by-id"``
    becomes ``"http://cbrain.com/casefile/rel/case-by-id"``.
    """
    if "://" in rel or rel in _STANDARD_RELS:
        return rel
    return CASEFILE_REL_PREFIX + rel
